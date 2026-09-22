"""Render real synthetic video/audio; never claim a YouTube download passed."""
import subprocess
import pytest
from highlight_mcp.core import Settings
from highlight_mcp.pipeline import render_clip, probe, youtube_failure


@pytest.mark.parametrize('height,aspect', [(1080,'16:9'),(1080,'9:16'),(720,'16:9'),(720,'9:16')])
def test_hd_render_keeps_audio_and_expected_dimensions(tmp_path,height,aspect):
    settings=Settings(tmp_path)
    source=tmp_path/'source.mp4'
    output=tmp_path/'clip.mp4'
    width=height*16//9
    subprocess.run([settings.binary('ffmpeg'),'-v','error','-f','lavfi','-i',f'testsrc2=size={width}x{height}:rate=12','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-c:v','libx264','-preset','ultrafast','-c:a','aac',str(source)],check=True)
    render_clip(settings,source,output,0,1.5,aspect,lambda:None)
    info=probe(settings,output,lambda:None)
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    audio=next(s for s in info['streams'] if s['codec_type']=='audio')
    expected=(width,height) if aspect=='16:9' else (height,width)
    assert (video['width'],video['height'])==expected
    assert video['codec_name']=='h264' and audio['codec_name']=='aac'
    assert int(audio['sample_rate'])==48000
    assert abs(float(info['format']['duration'])-1.5)<.15
    # A real decoder must accept the complete output, including audio.
    subprocess.run([settings.binary('ffmpeg'),'-v','error','-xerror','-i',str(output),'-f','null','-'],check=True)


@pytest.mark.parametrize('error,expected', [('Could not copy Chrome cookie database','database is locked'),('Failed to decrypt with DPAPI','session encryption'),('Sign in to confirm you are not a bot','sign-in verification')])
def test_known_auth_failures_are_not_transient_retries(error,expected):
    message,retry=youtube_failure(error)
    assert expected in message and retry is False
