"""Explicit Docker/VirtualBox control, MQTT and on-demand process diagnostics."""
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import tracemalloc
from ..config import env
from ..tools import S, _schema


def _run(argv):
    if not shutil.which(argv[0]):raise RuntimeError(f'{argv[0]} kurulu veya PATH içinde değil.')
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=25,shell=False)
    if p.returncode:raise RuntimeError(p.stderr[:1500] or f'Çıkış kodu {p.returncode}')
    return p.stdout[:12000]


def docker_manage(action='list',container=''):
    if action=='list':
        raw=_run(['docker','ps','-a','--format','{{json .}}'])
        return [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}',container):raise ValueError('Geçerli container kimliği gerekli.')
    if action=='inspect':
        raw=json.loads(_run(['docker','inspect',container]));return [{'Id':x['Id'],'Name':x['Name'],'State':x['State']} for x in raw]
    if action=='logs':return _run(['docker','logs','--tail','100',container])
    if action not in ('start','stop','restart'):raise ValueError('list/inspect/logs/start/stop/restart kullan.')
    return _run(['docker',action,container])


def vm_manage(action='list',name=''):
    if action=='list':return _run(['VBoxManage','list','vms'])
    if not re.fullmatch(r'[\w .-]{1,100}',name) or name.startswith('-'):raise ValueError('Geçersiz VM adı.')
    if action=='info':return _run(['VBoxManage','showvminfo',name,'--machinereadable'])
    if action=='start':return _run(['VBoxManage','startvm',name,'--type','headless'])
    command={'pause':'pause','resume':'resume','shutdown':'acpipowerbutton'}.get(action)
    if not command:raise ValueError('list/info/start/pause/resume/shutdown kullan.')
    return _run(['VBoxManage','controlvm',name,command])


def mqtt_message(action,topic,payload='',timeout=10):
    import paho.mqtt.client as mqtt
    host=env('MQTT_HOST');port=int(env('MQTT_PORT','1883'))
    if not host:raise RuntimeError('MQTT_HOST ayarla; MQTT_PORT/USER/PASSWORD/TLS isteğe bağlı.')
    if action not in ('read','publish') or not topic or len(topic)>512 or '\x00' in topic:raise ValueError('read/publish ve geçerli konu gerekli.')
    if action=='publish' and ('#' in topic or '+' in topic):raise ValueError('Yayın konusu joker içeremez.')
    if len(payload.encode())>65536:raise ValueError('Mesaj en fazla 64KB.')
    timeout=float(timeout)
    if not math.isfinite(timeout) or not 1<=port<=65535:raise ValueError('Geçersiz zaman aşımı/port.')
    timeout=max(1,min(timeout,20));done=threading.Event();box={}
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect_timeout=min(timeout,10)
    user=env('MQTT_USER')
    if user:client.username_pw_set(user,env('MQTT_PASSWORD'))
    if env('MQTT_TLS')=='1':client.tls_set()
    def connected(c,userdata,flags,reason,properties):
        if reason!=0:box['error']=str(reason);done.set();return
        if action=='read':c.subscribe(topic,qos=1)
        else:c.publish(topic,payload,qos=1,retain=False)
    def message(c,userdata,msg):
        box.update(topic=msg.topic,payload=msg.payload[:65536].decode('utf-8','replace'));done.set()
    def published(c,userdata,mid,reason,properties):
        if reason.is_failure:box['error']=str(reason)
        else:box['published']=True
        done.set()
    client.on_connect=connected;client.on_message=message;client.on_publish=published
    try:
        client.connect(host,port,keepalive=30);client.loop_start()
        if not done.wait(timeout):raise TimeoutError('MQTT yanıt süresi doldu.')
        if 'error' in box:raise RuntimeError(box['error'])
        return box
    finally:
        client.disconnect();client.loop_stop()


_samples=[]
_profile_lock=threading.Lock()

def runtime_diagnostics(action='sample'):
    import psutil
    p=psutil.Process()
    with _profile_lock:
        if action=='trace_start':
            if not tracemalloc.is_tracing():tracemalloc.start(10)
        elif action=='trace_stop':tracemalloc.stop()
        elif action not in ('sample','report'):raise ValueError('sample/report/trace_start/trace_stop kullan.')
        sample={'time':time.time(),'rss_bytes':p.memory_info().rss,'threads':p.num_threads(),'cpu_seconds':sum(p.cpu_times()[:2])}
        _samples.append(sample);del _samples[:-120]
        result={'current':sample,'sample_count':len(_samples),'rss_change_bytes':sample['rss_bytes']-_samples[0]['rss_bytes'],
                'uptime_seconds':time.time()-p.create_time(),'note':'RSS artışı tek başına bellek sızıntısı kanıtı değildir; GPU/başlatma ölçümü içermez.'}
        if tracemalloc.is_tracing():
            current,peak=tracemalloc.get_traced_memory();result['python_heap_bytes']=current;result['python_peak_bytes']=peak
            if action=='report':result['top_allocations']=[{'location':str(s.traceback),'bytes':s.size,'count':s.count} for s in tracemalloc.take_snapshot().statistics('lineno')[:10]]
        return result


TOOLS={
 'docker_manage':(docker_manage,_schema('Kurulu Docker daemon üzerinde container listeleme/inceleme/log/start/stop/restart. Silme, image çalıştırma veya shell yürütme yok.',{'action':S('işlem'),'container':S('kimlik veya ad')}),lambda a:a.get('action','list') in ('start','stop','restart')),
 'vm_manage':(vm_manage,_schema('Kurulu VirtualBox VM list/info/start/pause/resume/shutdown kontrolü; VM kurulumu yapmaz.',{'action':S('işlem'),'name':S('VM adı')}),lambda a:a.get('action','list') not in ('list','info')),
 'mqtt_message':(mqtt_message,_schema('Yapılandırılmış MQTT brokerdan tek mesaj oku veya QoS1 mesaj yayımla. .env MQTT_HOST/PORT/USER/PASSWORD/TLS.',{'action':S('read/publish'),'topic':S('konu'),'payload':S('mesaj'),'timeout':{'type':'number'}},['action','topic']),lambda a:a.get('action')=='publish'),
 'runtime_diagnostics':(runtime_diagnostics,_schema('Gerçek süreç RSS/CPU/thread örnekleri; isteğe bağlı Python heap izleme. sample/report/trace_start/trace_stop.',{'action':S('işlem')}),False),
}
