import json, subprocess
import pytest
from highlight_mcp.core import Service, Settings

@pytest.fixture
def recovery(tmp_path):
 service=Service(Settings(tmp_path), launch=False)
 job=service.call('highlight_create',{'url':'https://youtu.be/abcdefghijk'})['job_id']
 service.store.update(job,state='failed',stage='ingest')
 source=tmp_path/'host.mp4'
 subprocess.run([service.settings.binary('ffmpeg'),'-v','error','-f','lavfi','-i','color=size=1280x720:rate=10','-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','libx264','-preset','ultrafast','-c:a','aac',str(source)],check=True)
 return service,job,{'path':str(source),'source_url':'https://youtu.be/abcdefghijk','expected_duration_seconds':2,'method':'synthetic test fixture'}

def test_import_preserves_request_and_resumes(recovery):
 service,job,source=recovery
 request=service.store.get(job)['request']
 result=service.call('highlight_retry',{'job_id':job,'acquired_source':source})
 assert result['ok'],result
 saved=service.store.get(job)
 assert saved['state']=='queued' and saved['request']==request
 assert saved['source_acquisition']['quality_height']==720
 assert (service.settings.root/job/'source.mp4').is_file()
 assert json.loads((service.settings.root/job/'metadata.json').read_text())['duration']>0

@pytest.mark.parametrize('field,value',[('source_url','https://youtu.be/xxxxxxxxxxx'),('expected_duration_seconds',100),('path','missing.mp4')])
def test_reject_wrong_source_without_resuming(recovery,field,value):
 service,job,source=recovery
 source[field]=value
 result=service.call('highlight_retry',{'job_id':job,'acquired_source':source})
 assert not result['ok']
 assert service.store.get(job)['state']=='failed'
 assert not (service.settings.root/job/'source.mp4').exists()

def test_import_resumes_pipeline_without_metadata_network(recovery,monkeypatch):
 from highlight_mcp.pipeline import run
 import highlight_mcp.pipeline as pipeline
 service,job,source=recovery
 assert service.call('highlight_retry',{'job_id':job,'acquired_source':source})['ok']
 root=service.settings.root/job
 (root/'transcript.json').write_text(json.dumps([{'start':0,'end':2,'text':'fixture speech'}]))
 original=pipeline.command
 def guarded(args,*a,**kw):
  assert 'yt_dlp' not in args, 'Imported source must not redownload or refetch metadata'
  return original(args,*a,**kw)
 monkeypatch.setattr(pipeline,'command',guarded)
 run(service.settings,service.store,service.store.get(job),lambda:None)
 assert service.store.get(job)['state']=='awaiting_selection'

@pytest.mark.parametrize('height,audio',[(360,True),(720,False)])
def test_import_rejects_low_quality_or_missing_audio(recovery,height,audio):
 service,job,source=recovery
 args=[service.settings.binary('ffmpeg'),'-y','-v','error','-f','lavfi','-i',f'color=size={height*16//9}x{height}:rate=10']
 if audio: args+=['-f','lavfi','-i','sine=frequency=440']
 subprocess.run(args+['-t','2','-c:v','libx264','-preset','ultrafast',source['path']],check=True)
 assert not service.call('highlight_retry',{'job_id':job,'acquired_source':source})['ok']
 assert service.store.get(job)['state']=='failed'
