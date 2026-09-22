"""Host-agent recovery instructions; no fake download success or account access."""

def recovery_plan(job):
    if job['state'] != 'failed' or job['stage'] != 'ingest':
        return None
    error = (job.get('error') or '').lower()
    provider = job.get('youtube_access', 'not_attempted')
    common = [
        'Keep this job ID, source URL, user options and completed research. Do not recreate the job with defaults.',
        'Check cached source/transcript artifacts and installed yt-dlp, EJS and JS runtime. A cache must belong to this exact video and be valid; do not fabricate a usable file.',
        'Use host browser tools to inspect this exact video if available. Observe whether playback works; never infer this from the title alone.',
        'The host agent should acquire the full video using an available supported alternative, verify its identity and duration, then call highlight_retry on this job with acquired_source={path, source_url, expected_duration_seconds, method}. Do not repeat the same failed downloader/environment. Never bypass access restrictions. This is a host handoff, not an automatic download success.',
        'Continue independent background research and accessible timestamped comments/likes. Preserve sources and uncertainty. Do not shortlist before full-video transcript review.',
    ]
    if 'database is locked' in error:
        cause = 'browser_session_locked'
        action = 'Authorization is already present. Use the installed Highlight browser connector with Chrome open; if not installed, explain that setup is incomplete, not that the user must log in again. Do not force-close processes, ask permission again or request an MP4.'
    elif 'session encryption' in error:
        cause = 'browser_session_encryption'
        action = 'Do not disable browser encryption. Explain that this session cannot be read by the downloader and use only a supported authorized authentication method.'
    elif 'sign-in' in error or 'not a bot' in error:
        cause = 'youtube_authentication'
        action = 'If playback works in an authenticated browser, request narrowly scoped authorization for using that YouTube session in the downloader unless already granted. Do not extract cookies without authorization. Explain the single required action; do not demand an MP4. If browser playback also requires verification, hand that step to the user.'
    elif 'rate-limit' in error or '429' in error:
        cause = 'rate_limited'
        action = 'Do not retry immediately or rotate clients repeatedly. Explain cooldown; continue research. Resume the same job only after the condition changes. Do not claim a future retry is scheduled unless scheduling actually succeeded.'
    elif 'restricted' in error or 'unavailable' in error:
        cause = 'source_access'
        action = 'Verify source visibility in browser. Respect private, removed, membership and region restrictions; request only the missing access or a user-provided alternative when necessary.'
    else:
        cause = 'download_diagnostic'
        action = 'Inspect the specific downloader failure. Check runtime/dependency compatibility and configured provider readiness. Retry this job only after a concrete repair, not another identical attempt.'
    if provider == 'mweb_po_failed':
        common.append('The configured mweb PO fallback already failed. Do not repeat it unchanged.')
    else:
        common.append('Check whether the local PO fallback is configured and compatible; not_attempted does not mean it is available. Respect any tool-policy rejection; do not work around it.')
    return {'cause': cause, 'provider_attempt': provider, 'steps': common + [action],
            'completion': 'Verify a real source file with media probing before resuming transcription. Report completed work, exact remaining blocker and next action; file upload is an optional last resort, not the default.'}


def recovery_action(plan):
    return 'INGEST RECOVERY: ' + ' '.join(plan['steps']) + ' ' + plan['completion']
