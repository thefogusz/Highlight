"""Workflow evidence, not a claim that software can verify semantic understanding."""
from .core import Failure, digest, valid_range


def current_review(job, rows):
    version = digest({'rows': rows, 'duration': job['duration']})
    review = job.get('story_review', {})
    if review.get('version') != version:
        return {'version': version, 'read_through': 0, 'context_progress': {}, 'contexts': []}
    return review


def story_response(job, rows, review, story=None):
    complete = bool(rows) and review['read_through'] >= len(rows)
    if story is not None:
        if not complete:
            raise Failure('INVALID_STATE', 'Read all full-video transcript pages before saving a story. Focus ranges only limit output clips.')
        research = story.get("background_research") or job["request"].get("background_research")
        if not research:
            raise Failure("INVALID_STATE", "Research the exact video background with host web tools before selecting. Supply story.background_research with sources, or explicitly record unavailable and its reason. Never invent browsing evidence.")
        story = {**story, "background_research": research}
        ids = set()
        for topic in story['topics']:
            if topic['topic_id'] in ids or not valid_range(topic['start_seconds'], topic['end_seconds'], job['duration']):
                raise Failure('INVALID_RANGE', 'Story topics need unique IDs and valid source timestamps.')
            ids.add(topic['topic_id'])
            text = ''.join(r['text'] for r in rows if r['end'] > topic['start_seconds'] and r['start'] < topic['end_seconds'])
            normalize = lambda value: ''.join(value.split())
            if normalize(topic['evidence_quote']) not in normalize(text):
                raise Failure('INVALID_RANGE', 'Topic evidence_quote must appear in transcript within the topic range; do not invent quotes.')
        topics = {t['topic_id']: t for t in story['topics']}
        seen = set()
        for moment in story['candidate_moments']:
            a, b = moment['start_seconds'], moment['end_seconds']
            topic = topics.get(moment['topic_id'])
            if not valid_range(a, b, job['duration']) or not topic or not topic['start_seconds'] <= a < b <= topic['end_seconds']:
                raise Failure('INVALID_RANGE', 'Candidate must belong to a reviewed topic and original source timeline.')
            if (a, b) in seen:
                raise Failure('INVALID_RANGE', 'Duplicate candidate timestamps; deduplicate before reporting counts.')
            seen.add((a, b))
        story_id = digest({'version': review['version'], 'story': story})
        if story_id != review.get('story_id'):
            review.update(story=story, story_id=story_id, contexts=[], context_progress={})
    return {'job_id': job['id'], 'coverage_complete': complete,
            'delivered_segments': review['read_through'], 'total_segments': len(rows),
            'story_id': review.get('story_id'), 'story': review.get('story'),
            'next_action': 'After saving the whole-story map, read boundary context for selected moments, then submit story_id and each topic_id to highlight_render. Delivery coverage is not proof of comprehension.' if complete else 'Read full-video highlight_transcript pages in order. Do not shortlist before the full story has been read.'}


def require_review(review, story_id, clips, duration):
    if not review.get('story') or not review['story'].get('background_research') or story_id != review.get('story_id'):
        raise Failure('INVALID_STATE', 'Save a current whole-story review with highlight_story before rendering. A stale story_id is not valid.')
    topics = {t['topic_id']: t for t in review['story']['topics']}
    candidates = review['story'].get('candidate_moments', [])
    for clip in clips:
        index = clip.get('candidate_index')
        if type(index) is not int or not 0 <= index < len(candidates):
            raise Failure('INVALID_STATE', 'Save ranked candidate_moments and reference a candidate_index before preview or render.')
        candidate = candidates[index]
        if candidate['topic_id'] != clip.get('topic_id') or not candidate['start_seconds'] <= clip['start_seconds'] < clip['end_seconds'] <= candidate['end_seconds']:
            raise Failure('INVALID_RANGE', 'Clip must fit its saved candidate. Update the ledger before changing candidate boundaries.')
        topic = topics.get(clip.get('topic_id'))
        a, b = clip['start_seconds'], clip['end_seconds']
        if not topic or not topic['start_seconds'] <= a < b <= topic['end_seconds']:
            raise Failure('INVALID_RANGE', 'Every clip must belong to a reviewed story topic. Update the story map if necessary.')
        for boundary in (a, b):
            left, right = max(0, boundary-15), min(duration, boundary+15)
            if not any(x <= left and y >= right for x, y in review['contexts']):
                raise Failure('INVALID_STATE', f'Read boundary context around {boundary} seconds (at least {left}–{right}) after saving the story, including all context pages. Subtitle times are not word boundaries.')
