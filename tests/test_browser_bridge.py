from workflow_support import OFFLINE_RESEARCH
import json,os,time,subprocess,sys,struct
import pytest
from highlight_mcp.core import Settings,Service
from highlight_mcp.browser_bridge import crypt,handle,request_session,read_session,ORIGIN

pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI bridge')

def prepared(tmp_path):
 service=Service(Settings(tmp_path),launch=False)
 job=service.call('highlight_create',{'background_research': OFFLINE_RESEARCH, **{'url':'https://youtu.be/abcdefghijk'}})['job_id']
 service.store.update(job,state='running',stage='ingest')
 folder=tmp_path/job;folder.mkdir(exist_ok=True)
 (folder/'browser-request.json').write_text(json.dumps({'nonce':'testnonce','expires':time.time()+60}))
 return service,job,folder

def test_dpapi_roundtrip_and_ciphertext():
 secret=b'fixture-session-secret'
 encrypted=crypt(secret)
 assert secret not in encrypted
 assert crypt(encrypted,True)==secret

def test_session_scoped_encrypted_and_pending(tmp_path):
 service,job,folder=prepared(tmp_path)
 request=handle(service.settings,{'type':'poll'})['requests'][0]
 message={'type':'session',**request,'cookies':[{'domain':'.youtube.com','name':'fixture','value':'secret-fixture','path':'/','secure':True}]}
 assert handle(service.settings,message)=={'ok':True}
 path=folder/'browser-session.bin'
 assert b'secret-fixture' not in path.read_bytes()
 assert read_session(path)['url']=='https://www.youtube.com/watch?v=abcdefghijk'
 message['nonce']='wrong'
 with pytest.raises(ValueError):handle(service.settings,message)
 assert handle(service.settings,{'type':'disconnect'})=={'ok':True}
 assert not path.exists()

@pytest.mark.parametrize('domain',['evil.com','.youtube.com.evil.com','google.com'])
def test_reject_unrelated_cookies(tmp_path,domain):
 service,job,folder=prepared(tmp_path)
 with pytest.raises(ValueError):handle(service.settings,{'type':'session','job_id':job,'nonce':'testnonce','cookies':[{'domain':domain,'name':'x','value':'y','path':'/'}]})
 assert not (folder/'browser-session.bin').exists()

def test_absent_bridge_does_not_delay_job(tmp_path):
 service,job,folder=prepared(tmp_path)
 assert request_session(service.settings,service.store.get(job),lambda:None) is None

def test_native_protocol_real_subprocess(tmp_path):
 message=json.dumps({'type':'poll'}).encode()
 env={**os.environ,'HIGHLIGHT_DATA_DIR':str(tmp_path),'PYTHONPATH':str(__import__('pathlib').Path('src').resolve())}
 result=subprocess.run([sys.executable,'-m','highlight_mcp.browser_bridge',ORIGIN],input=struct.pack('<I',len(message))+message,capture_output=True,env=env,timeout=10)
 assert result.returncode==0,result.stderr
 n=struct.unpack('<I',result.stdout[:4])[0]
 assert json.loads(result.stdout[4:4+n])=={'requests':[]}
 rejected=subprocess.run([sys.executable,'-m','highlight_mcp.browser_bridge','chrome-extension://wrong/'],input=b'',capture_output=True,env=env,timeout=10)
 assert rejected.returncode==1 and not rejected.stdout

def test_request_response_handoff(tmp_path):
 import threading
 service,job,folder=prepared(tmp_path)
 (service.settings.root/'browser-connected').touch()
 def respond():
  deadline=time.monotonic()+5
  while time.monotonic()<deadline:
   requests=handle(service.settings,{'type':'poll'})['requests']
   if requests and requests[0]['nonce']!='testnonce':
    handle(service.settings,{'type':'session',**requests[0],'cookies':[{'domain':'.youtube.com','name':'fixture','value':'not-a-real-session','path':'/','secure':True}]})
    return
   time.sleep(.05)
 thread=threading.Thread(target=respond);thread.start()
 path=request_session(service.settings,service.store.get(job),lambda:None,timeout=5)
 thread.join(5)
 assert path and read_session(path)['cookies'][0]['name']=='fixture'
 assert not (folder/'browser-request.json').exists()

def test_downloader_uses_in_memory_jar_for_exact_video(tmp_path,monkeypatch):
 from highlight_mcp import browser_download
 import yt_dlp,http.cookiejar
 payload={'url':'https://www.youtube.com/watch?v=abcdefghijk','cookies':[{'domain':'.youtube.com','name':'fixture','value':'not-real','path':'/','secure':True}]}
 monkeypatch.setattr(browser_download,'read_session',lambda path:payload)
 monkeypatch.setattr(sys,'argv',['browser_download','unused'])
 monkeypatch.setattr(yt_dlp,'parse_options',lambda args:(None,None,[payload['url']],{}))
 class Downloader:
  def __init__(self,options):
   assert 'cookiefile' not in options and 'cookiesfrombrowser' not in options
   self.cookiejar=http.cookiejar.CookieJar()
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def download(self,urls):
   assert urls==[payload['url']]
   assert next(iter(self.cookiejar)).value=='not-real'
   return 0
 monkeypatch.setattr(yt_dlp,'YoutubeDL',Downloader)
 assert browser_download.main()==0
 monkeypatch.setattr(yt_dlp,'parse_options',lambda args:(None,None,['https://www.youtube.com/watch?v=xxxxxxxxxxx'],{}))
 with pytest.raises(ValueError):browser_download.main()
