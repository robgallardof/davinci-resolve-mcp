import subprocess
from types import SimpleNamespace
import pytest
from PIL import Image
from resolve_forge.domain import composition
from resolve_forge.services import composition_service as service


def test_geometry_and_invalid_crop():
    for count in range(2,6):
        p=composition.plan([{'duration_s':2,'sources':[{'source':str(i)} for i in range(count)]}],{'source':'audio'},1080,1920)
        assert len(p['segments'][0]['sources'])==count
        assert sum((s['screen'][2]-s['screen'][0])*(s['screen'][3]-s['screen'][1]) for s in p['segments'][0]['sources'])==pytest.approx(1)
    for crop in ([.8,0,.2,1],[0,0,1.1,1],[0,0,float('nan'),1]):
        with pytest.raises(ValueError):
            composition.plan([{'duration_s':1,'sources':[{'source':'a','crop':crop}]}],{'source':'a'},100,200)
    with pytest.raises(ValueError,match='explicit'):
        composition.plan([{'duration_s':1,'sources':[{'source':'a'}]}],None,100,200)


@pytest.fixture
def assets(tmp_path,monkeypatch):
    monkeypatch.setattr(service,'DEFAULT_OUTPUT',tmp_path/'out')
    monkeypatch.setattr(service.formats,'get',lambda key:SimpleNamespace(key='test',width=160,height=240,fps=10))
    exe=service.ffmpeg_executable()
    video=tmp_path/'moving.mp4'
    subprocess.run([exe,'-hide_banner','-loglevel','error','-nostdin','-n','-f','lavfi','-i','color=red:s=160x120:r=10:d=1','-f','lavfi','-i','color=blue:s=160x120:r=10:d=1','-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]','-map','[v]','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True,capture_output=True)
    audio=tmp_path/'master.wav'
    subprocess.run([exe,'-hide_banner','-loglevel','error','-nostdin','-n','-f','lavfi','-i','sine=frequency=880:duration=4',str(audio)],check=True,capture_output=True)
    stills=[]
    for i,color in enumerate(['green','yellow','magenta','cyan']):
        path=tmp_path/f'{i}.png'
        Image.new('RGB',(160,120),color).save(path)
        stills.append(str(path))
    return str(video),str(audio),stills


def pixel(file,time,point):
    import io
    frame=service._run(['-ss',str(time),'-i',file,'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
    return Image.open(io.BytesIO(frame)).getpixel(point)


@pytest.mark.parametrize('count',[2,3,4,5])
def test_distinct_sources_offsets_stills_and_audio(assets,count):
    video,audio,stills=assets
    segments=[{'duration_s':.8,'sources':[{'source':video,'start_s':1,'fit':'cover'}]+[{'source':s,'fit':'cover'} for s in stills[:count-1]]}]
    prepared=service._prepare(None,segments,{'source':audio,'start_s':.25},'test')
    built=service.build(None,segments,{'source':audio,'start_s':.25},'composition',dry_run=False,reviewed=True)
    for item in prepared['segments'][0]['sources']:
        r=item['screen']; point=(int((r[0]+r[2])*80),int((r[1]+r[3])*120))
        rgb=pixel(built['file'],.4,point)
        expected=(0,0,255) if item['source']==video else Image.open(item['source']).getpixel((10,10))
        assert all(abs(a-b)<15 for a,b in zip(rgb,expected))
    import numpy as np
    signal=np.frombuffer(service._run(['-i',built['file'],'-vn','-ac','1','-ar','8000','-f','f32le','-']),dtype='<f4')
    freq=np.fft.rfftfreq(len(signal),1/8000)[np.argmax(abs(np.fft.rfft(signal)))]
    assert freq==pytest.approx(880,abs=4)


def test_preview_and_rejections(assets):
    video,audio,stills=assets
    segments=[{'duration_s':.6,'layout':'hero_support','sources':[{'source':video},{'source':stills[0]}]}]
    p=service.plan(None,segments,{'source':audio},'test')
    assert Image.open(p['sheet']).width==1080
    assert len(p['sample_times_s'])==3 and service._probe(p['preview_video'])['audio']
    with pytest.raises(ValueError,match='reviewed'):
        service.build(None,segments,{'source':audio},'asset',dry_run=False)
    with pytest.raises(ValueError,match='duration'):
        service.build(None,[{'duration_s':3,'sources':[{'source':video}]}],{'source':audio},'asset')
    with pytest.raises(ValueError,match='shorter'):
        service.build(None,[{'duration_s':1,'sources':[{'source':stills[0]}]}],{'source':audio,'start_s':3.5},'asset')
    with pytest.raises(ValueError,match='basename'):
        service.build(None,segments,{'source':audio},'../escape')
    with pytest.raises(ValueError,match='no audio'):
        service.build(None,segments,{'source':video},'asset')
