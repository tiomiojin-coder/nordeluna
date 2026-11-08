"""Build a LOCAL reviewable RPG Maker XP map pack. Does not install or publish."""
import collections
import hashlib
import json
import math
import re
import importlib.util
import shutil
import zipfile
import zlib
from pathlib import Path
import sys
from rgss_map_tools import MapCodec,MapRenderer,ROOT,DEFAULT_GAME,graphic_path

OUT=ROOT/'build/social-maps'
FIXTURES=ROOT/'scripts/fixtures'


def tile(x,y):return 384+y*8+x


class Grid:
    def __init__(self,mid,name,w,h,tileset,base,bgm,metadata):
        self.plan=dict(id=mid,name=name,width=w,height=h,tileset_id=tileset,bgm=bgm,values=[base]*(w*h)+[0]*(w*h*2),events=[])
        self.w,self.h,self.meta=w,h,metadata
        self.occupied=set()
        self.transfers=[]
    def put(self,x,y,z,value):
        if not (0<=x<self.w and 0<=y<self.h):raise ValueError(f'Placement outside map {self.plan["id"]}: {x},{y}')
        self.plan['values'][(z*self.h+y)*self.w+x]=value
    def rect(self,x,y,w,h,value,z=0):
        for yy in range(y,y+h):
            for xx in range(x,x+w):self.put(xx,yy,z,value)
    def object(self,sx,sy,w,h,x,y,layer=None):
        for dy in range(h):
            for dx in range(w):
                value=tile(sx+dx,sy+dy)
                z=layer if layer is not None else (2 if self.meta['priorities']['values'][value]>0 else 1)
                if z>0 and self.plan['values'][(z*self.h+y+dy)*self.w+x+dx]:
                    raise ValueError(f'Object overlap at {x+dx},{y+dy}, layer {z+1}')
                self.put(x+dx,y+dy,z,value)
    def path(self,points,value=489):
        for x,y in points:self.put(x,y,0,value)
    def area(self,x,y,w,h):return {(xx,yy) for yy in range(y,y+h) for xx in range(x,x+w)}
    def pavement(self,points):
        for x,y in points:
            # Existing Salvador pavement, with its intact 3x3 edge pieces.
            cx=0 if (x-1,y) not in points else 2 if (x+1,y) not in points else 1
            cy=12 if (x,y-1) not in points else 14 if (x,y+1) not in points else 13
            self.put(x,y,0,tile(cx,cy))
    def rug(self,x,y,w,h,sx,sy):
        for dy in range(h):
            for dx in range(w):
                a=0 if dx==0 else 2 if dx==w-1 else 1
                b=0 if dy==0 else 2 if dy==h-1 else 1
                self.put(x+dx,y+dy,0,tile(sx+a,sy+b))
    def event(self,eid,name,x,y,text=None,action=None,args=(),character='',trigger=0,through=False,hidden=False,direction=2):
        if eid in {e['id'] for e in self.plan['events']}:raise ValueError('Duplicate event ID')
        commands=[]
        if text:
            for message in text if isinstance(text,list) else [text]:commands.append([101,0,[message]])
        if action:
            arguments=', '.join(json.dumps(a,ensure_ascii=False) for a in args)
            script=f'NordelunaOnline::SocialMaps.call(:{action}'+(', '+arguments if arguments else '')+')'
            commands.append([355,0,[script]])
        commands.append([0,0,[]])
        self.plan['events'].append(dict(id=eid,name=name,x=x,y=y,commands=commands,character=character,trigger=trigger,through=through,hidden=hidden,direction=direction))
        if character and not through:self.occupied.add((x,y))
    def sign(self,eid,name,x,y,text=None,action=None,args=()):
        self.object(5,20,1,2,x,y-1)
        self.event(eid,name,x,y,text=text,action=action,args=args)
    def warp(self,eid,name,x,y,mid,tx,ty,direction):
        self.event(eid,name,x,y,action='door',args=(mid,tx,ty,direction),trigger=1,through=True)
        self.transfers.append(dict(event=eid,source=[x,y],target=[mid,tx,ty,direction]))


def make_plaza(meta):
    g=Grid(39,'Praça Central',70,70,34,385,'Praça-do-Interior',meta)
    paths=g.area(31,7,8,57)|g.area(7,29,56,7)|g.area(9,8,18,17)|g.area(44,8,18,18)
    paths|=g.area(12,24,8,9)|g.area(49,24,8,9)
    paths|={(x,y) for y in range(23,47) for x in range(23,47) if (x-34.5)**2+(y-34.5)**2<=11.5**2}
    # A continuous loop serves both gardens, plus clear approaches to each stone.
    paths|=g.area(9,41,4,18)|g.area(23,41,4,18)|g.area(9,41,18,3)|g.area(9,56,18,3)
    paths|=g.area(43,41,18,3)|g.area(43,56,18,3)|g.area(43,41,4,18)|g.area(57,41,4,18)
    paths|=g.area(12,47,12,5)|g.area(46,47,12,5)|g.area(23,48,24,4)
    g.pavement(paths)
    # An inlaid crescent uses two existing pavements, not a new graphic/tileset.
    for y in range(26,44):
        for x in range(26,44):
            dx,dy=x-34.5,y-34.5
            if dx*dx+dy*dy<=8.5**2:
                g.put(x,y,0,478)
                if dx*dx+dy*dy<=7.5**2 and (dx-2.5)**2+(dy+1)**2>=6.5**2:
                    g.put(x,y,0,489)
    # Forest border uses whole 2x3 deciduous trees from Salvador (no palms/beach).
    for y in [0,3,64,67]:
        for x in range(0,70,2):g.object(1,24,2,3,x,y)
    for x in [0,2,66,68]:
        for y in range(6,63,3):g.object(1,24,2,3,x,y)
    # Complete source facades, with canopy/roof priorities carried intact.
    g.object(0,350,8,8,13,10)
    g.object(0,243,7,11,48,9)
    # Reception kiosk and the central lunar fountain use a complete prefab each.
    g.object(4,206,4,4,33,5)
    g.object(0,105,3,4,33,31)
    # Four small flower gardens frame the monument, while the axes stay clear.
    for cx,cy in [(26,26),(41,26),(26,41),(41,41)]:
        for dx in [0,1]:g.object(4+dx,22,1,1,cx+dx,cy)
        g.object(7,21,1,1,cx,cy+1)
        g.object(7,21,1,1,cx+1,cy+1)
    # Interior greenery deliberately avoids the door approaches and arrival.
    for x,y in [(7,8),(25,8),(7,21),(25,21),(43,8),(60,8),(43,23),(60,23),
                (7,38),(28,56),(41,56),(60,38),(7,60),(60,60)]:g.object(1,24,2,3,x,y)
    for x,y in [(11,37),(53,37),(28,17),(40,17),(28,59),(40,59)]:g.object(0,100,1,3,x,y)
    for x,y in [(10,27),(22,27),(46,27),(58,27),(28,45),(38,45),(13,59),(52,59)]:g.object(6,128,2,2,x,y)
    # A small constellation garden: four monoliths with a local phase puzzle.
    for x,y in [(15,45),(20,45),(20,53),(15,53)]:g.object(5,44,1,2,x,y-1)
    for x,y in [(16,44),(18,44),(16,54),(18,54)]:g.object(4,22,1,1,x,y)
    for x,y in [(16,45),(18,45),(16,53),(18,53)]:g.object(5,22,1,1,x,y)
    # A convivial garden, with a large shade tree and benches around a clear path.
    g.object(3,32,5,5,48,44)
    for x,y in [(47,53),(53,53)]:g.object(6,128,2,2,x,y)
    for x,y in [(11,12),(24,12),(46,13),(58,13),(30,55),(38,55)]:g.object(4,20,1,2,x,y)
    g.warp(1,'Porta do Coliseu Lunar',17,17,40,19,31,8)
    g.warp(2,'Porta do Mercado Global',51,19,41,18,25,8)
    g.event(3,'Recepção da Praça',35,11,action='reception',character='NPC 3')
    g.event(4,'Retorno à campanha',36,59,action='leave',character='NPC04')
    g.event(5,'Curadora da Fonte Lunar',30,34,text='A água guarda o reflexo do céu, mas são os encontros que dão vida à praça.',action='moon_clock',character='NPC10')
    g.event(6,'Animador dos encontros',42,33,action='emote_lesson',character='trArtist')
    g.event(7,'Viajante e seu parceiro',46,51,action='partner_story',character='NPC13')
    g.event(8,'Observadora das fases',11,49,text=['Quatro pedras guardam o ciclo da lua. Comece pela lua que ainda não ilumina a noite.','O brilho cresce, torna-se inteiro e depois se recolhe. Caminhe pelo jardim e descubra a ordem.'],character='NPC42')
    g.event(9,'Guia dos desafios',21,20,text='O Coliseu fica logo ali. A batalha só começa depois que você e seu adversário confirmarem a sala.',character='trRanger_M')
    g.event(10,'Guia das trocas',57,23,text='No Mercado Global, você combina uma troca por sala e confere os dois Pokémon antes de confirmar.',character='NPC14')
    g.sign(11,'Placa do Coliseu',22,23,'COLISEU LUNAR\nEncontros, equipes e desafios entre treinadores.')
    g.sign(12,'Placa do Mercado',47,24,'MERCADO GLOBAL\nCentral de trocas e apoio ao viajante.')
    g.sign(13,'Mapa da Praça',32,57,action='directions')
    g.sign(14,'Inscrição da Fonte',35,37,'FONTE LUNAR\nQue cada chegada seja o começo de uma nova amizade.')
    g.sign(15,'Placa do Jardim',10,54,'JARDIM DAS FASES\nToque as quatro pedras na ordem do ciclo lunar.')
    g.event(16,'Pedestal da Lua Nova',15,45,action='phase_stone',args=(0,))
    g.event(17,'Pedestal da Lua Crescente',20,45,action='phase_stone',args=(1,))
    g.event(18,'Pedestal da Lua Cheia',20,53,action='phase_stone',args=(2,))
    g.event(19,'Pedestal da Lua Minguante',15,53,action='phase_stone',args=(3,))
    g.event(20,'Aprendiz de apelidos',26,32,text='Aqui usamos o nick online. O nome de Leo Farias continua sendo o mesmo na história.',character='NPC07')
    g.event(21,'Amiga das descobertas',54,50,text='Experimente conversar com alguém que trouxe um parceiro diferente. Cada região tem uma surpresa!',character='NPC22')
    g.event(22,'Cuidadora dos viajantes',28,50,action='heal',character='NPC03')
    g.event(30,'Memória local do Jardim das Fases',6,6,through=True,hidden=True)
    return g


def room(mid,name,w,h,bgm,meta,floor=649):
    g=Grid(mid,name,w,h,24,48,bgm,meta)
    g.rect(3,5,w-6,h-8,floor)
    # Complete striped-wall body; the very top and side pieces match Inside Geral.
    for x in range(3,w-3):
        for dy,sy in enumerate([201,202,203]):g.put(x,2+dy,0,tile(4,sy))
    for y in range(2,h-3):
        g.put(2,y,0,tile(7,202))
        g.put(w-3,y,0,tile(7,202))
    # Entrance is a complete blue doormat, entirely inside the room floor.
    g.rug(w//2-1,h-5,3,2,0,386)
    return g


def counter(g,x,y,w,color=4):
    for dx in range(w):
        sx=color if dx==0 else color+2 if dx==w-1 else color+1
        g.put(x+dx,y,2,tile(sx,356))
        g.put(x+dx,y+1,1,tile(sx,357))


def make_coliseum(meta):
    g=room(40,'Coliseu Lunar',40,36,'Gym',meta)
    g.rug(12,7,16,13,0,386)
    g.object(0,404,3,3,18,8,layer=0)
    g.object(3,407,3,3,18,12,layer=0)
    g.object(3,401,3,3,18,16,layer=0)
    for x in [5,32]:
        for y in [7,13,19]:g.object(2,490,3,2,x,y)
    for x,y in [(4,5),(34,5),(4,29),(34,29)]:g.object(4,578,1,2,x,y)
    # Left and right preparation desks keep the central approach open.
    counter(g,5,26,8,color=4);counter(g,27,26,8,color=0)
    g.object(2,490,3,2,4,22)
    g.object(0,414,1,3,34,21)
    for x in [9,28]:g.object(0,259,2,1,x,3)
    g.object(1,564,1,1,19,4)
    g.event(1,'Balcão de desafios',8,26,action='battle_desk',character='trRanger_M')
    g.event(2,'Preparadora de equipes',30,26,action='team_info',character='NPC10')
    g.event(3,'Cuidadora do Coliseu',7,23,action='heal',character='NPC03')
    g.event(4,'Terminal de armazenamento',34,23,action='pc')
    g.event(5,'Treinadora de batalhas duplas',10,13,text=['Em duplas, cada Pokémon tem seu próprio comando e pode precisar de um alvo diferente.','Confirme equipe e regras antes de começar. A posição nesta arena é apenas um ponto de encontro.'],character='trRanger_F')
    g.event(6,'Treinador paciente',29,13,text='Vitória por queda não é vitória. Se a conexão for interrompida, procure o aviso do Online antes de criar outra sala.',character='NPC13')
    g.event(7,'Estudiosa de habilidades',9,20,text='Trocar uma habilidade pode mudar toda a estratégia. Observe a identificação da habilidade e os efeitos de campo.',character='NPC42')
    g.event(8,'Fã de parceiros raros',30,20,action='partner_story',character='NPC22')
    g.event(9,'Mural das regras',19,4,text=['COLISEU LUNAR\nPrepare sua equipe e combine um desafio no balcão.','O anfitrião escolhe nível, quantidade de Pokémon, lendários e formato. Os dois jogadores precisam usar versões compatíveis.'])
    g.event(10,'Boas-vindas da arena',19,22,text='O mosaico lunar é nosso ponto de reunião. Pisar nele não inicia nenhuma batalha.',character='NPC07')
    for dx in range(3):g.warp(20+dx,'Saída para a Praça',19+dx,32,39,17,19,2)
    return g


def make_market(meta):
    g=room(41,'Mercado Global',38,30,'Mercado de Fortaleza',meta,floor=736)
    g.rug(16,10,6,15,0,386)
    counter(g,13,7,12,color=4)
    for x in [8,28]:g.object(0,259,2,1,x,3)
    g.object(1,564,1,1,18,4)
    # Complete shelves, island displays and waiting-room furniture.
    for x,y in [(5,10),(8,10),(27,10),(30,10)]:g.object(0,556,3,2,x,y)
    for x,y in [(6,16),(27,16)]:g.object(3,554,2,4,x,y)
    counter(g,5,21,8,color=0)
    g.object(0,414,1,3,30,20)
    g.object(2,490,3,2,23,22)
    for x,y in [(4,5),(33,5),(4,24),(33,24)]:g.object(5,578,1,2,x,y)
    g.event(1,'Balcão de trocas diretas',18,7,action='trade_desk',character='NPC14')
    g.event(2,'Mercadora de viagem',8,21,action='local_shop',character='NPC03')
    g.event(3,'Terminal de armazenamento',30,22,action='pc')
    g.event(4,'Orientadora das trocas',14,13,text=['Confira nome, espécie, nível, shiny, item e treinador original antes de confirmar.','Não envie o Pokémon por fora do sistema. A troca por sala usa confirmação, comprovante e recuperação.'],character='NPC10')
    g.event(5,'Colecionador de histórias',24,15,action='partner_story',character='NPC13')
    g.event(6,'Organizadora do encontro',23,23,text='Combine a troca pelo chat da sua sala. O balcão não mantém anúncios globais nem faz entregas automáticas.',character='NPC22')
    g.event(7,'Catálogo de viagem',6,18,text='Suprimentos de viagem: Poké Bolas e itens de recuperação. A mercadora atende no balcão ao sul.')
    g.event(8,'Arquivo de dicas',28,18,text='Um Pokémon especial tem mais do que uma aparência: confira também sua origem e os detalhes na confirmação da troca.')
    g.event(9,'Quadro do Mercado',18,4,text='MERCADO GLOBAL\nBalcão de trocas ao norte; itens de viagem a sudoeste; terminal de armazenamento a sudeste.')
    g.event(10,'Visitante cuidadoso',10,14,text='Deixo espaço na equipe e confiro o save antes de uma troca. Se algo ficar pendente, uso a recuperação do Online.',character='NPC07')
    for dx in range(3):g.warp(20+dx,'Saída para a Praça',17+dx,26,39,51,21,2)
    return g


def map_metadata(codec,grids):
    source=(DEFAULT_GAME/'_extracted_scripts/139_MapMetadata.rb').read_text(encoding='utf-8')
    start=source.index('    def initialize(hash)')
    end=source.index('\n    end',start)+len('\n    end')
    codec.ruby.load_source('module GameData;class MapMetadata;\n'+source[start:end]+'\nend;end','actual Essentials map metadata constructor')
    codec.read('Data/map_metadata.dat','map_metadata')
    codec.ruby.evaluate('''$original_metadata=Marshal.load(Marshal.dump($map_metadata))
[[39,'Praça Central',true],[40,'Coliseu Lunar',false],[41,'Mercado Global',false]].each do |id,name,outdoor|
 $map_metadata[id]=GameData::MapMetadata.new(id: id,real_name: name,outdoor_map: outdoor,
  announce_location: true,can_bicycle: false,snap_edges: true,battle_background: 'city')
end
raise 'Unrelated metadata changed' unless $original_metadata.reject { |id,_| [39,40,41].include?(id) }.all? { |id,m| Marshal.dump(m)==Marshal.dump($map_metadata[id]) }
'ready' ''')
    codec.dump('$map_metadata',OUT/'Data/map_metadata.dat')
    raw=(DEFAULT_GAME/'PBS/map_metadata.txt').read_bytes()
    bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text=raw[len(bom):].decode('utf-8')
    newline='\r\n' if '\r\n' in text else '\n'
    replacements={}
    for g in grids:
        p=g.plan;mid=p['id']
        lines=[f'[{mid:03d}]',f'Name = {p["name"]}',f'Outdoor = {"true" if mid==39 else "false"}',
               'ShowArea = true','Bicycle = false','SnapEdges = true','BattleBack = city','#-------------------------------']
        replacements[mid]=newline.join(lines)+newline
    blocks=re.split(r'(?m)(?=^\[\d+\])',text)
    found=set();output=[]
    for block in blocks:
        section=re.match(r'^\[(\d+)\]',block)
        mid=int(section.group(1)) if section else None
        if mid in replacements:output.append(replacements[mid]);found.add(mid)
        else:output.append(block)
    output.extend(replacements[mid] for mid in replacements if mid not in found)
    destination=OUT/'PBS/map_metadata.txt';destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(bom+''.join(output).encode('utf-8'))


def compile_online(codec,sources,output):
    entries=[]
    for name,body in sorted(sources.items()):
        codec.ruby.evaluate('RubyVM::InstructionSequence.compile(['+json.dumps(body.hex())+'].pack("H*").force_encoding("UTF-8"));"valid"')
        entries.append('['+json.dumps(name)+',['+json.dumps(zlib.compress(body).hex())+'].pack("H*")]')
    original=(DEFAULT_GAME/'Data/PluginScripts.rxdata').read_bytes().hex()
    codec.ruby.evaluate('''$plugin_bundle=Marshal.load(['''+json.dumps(original)+'''].pack('H*'))
$index=$plugin_bundle.index { |p| p[0]=='Nordeluna Online' }
raise 'Online plugin is missing' unless $index
$unchanged_plugins=Marshal.dump($plugin_bundle.reject { |p| p[0]=='Nordeluna Online' })
$plugin_bundle[$index]=[$plugin_bundle[$index][0],$plugin_bundle[$index][1].dup,['''+','.join(entries)+''']]
raise 'Unrelated plugin changed' unless $unchanged_plugins==Marshal.dump($plugin_bundle.reject { |p| p[0]=='Nordeluna Online' })
'ready' ''')
    codec.dump('$plugin_bundle',output)


def packages(codec):
    maintained=ROOT/'game-plugins/Nordeluna Online'
    sources={p.name:p.read_bytes() for p in (DEFAULT_GAME/'Plugins/Nordeluna Online').glob('*.rb')}
    sources.update({p.name:p.read_bytes() for p in maintained.glob('*.rb')})
    for name in ['016_IdentityAndAreas.rb','020_SocialMaps.rb']:
        target=OUT/'Plugins/Nordeluna Online'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(sources[name])
    compile_online(codec,sources,OUT/'Data/PluginScripts.rxdata')
    activation=OUT/'online-activation'
    variant=dict(sources)
    text=variant['016_IdentityAndAreas.rb'].decode('utf-8')
    text=text.replace('COLISEUM_MAP_ID = nil','COLISEUM_MAP_ID = 40').replace('MARKET_MAP_ID = nil','MARKET_MAP_ID = 41')
    variant['016_IdentityAndAreas.rb']=text.encode('utf-8')
    target=activation/'Plugins/Nordeluna Online/016_IdentityAndAreas.rb';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(variant['016_IdentityAndAreas.rb'])
    compile_online(codec,variant,activation/'Data/PluginScripts.rxdata')
    spec=importlib.util.spec_from_file_location('social_server_package',ROOT/'scripts/package-discloud.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    builder.package('nordeluna-online',activation/'Nordeluna-Online-Mapas-39-40-41-Discloud.zip',dict(plaza=39,coliseum=40,market=41))
    (activation/'online-areas.json').write_text(json.dumps(dict(plaza=39,coliseum=40,market=41)),encoding='utf-8')
    shutil.copyfile(ROOT/'docs/social-maps.md',OUT/'LEIA-ME.md')
    bundle=OUT/'Nordeluna-Mapas-Local.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as archive:
        for folder in ['Data','PBS','Plugins']:
            for path in sorted((OUT/folder).rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(OUT).as_posix())
        archive.write(OUT/'LEIA-ME.md','LEIA-ME.md')
    with zipfile.ZipFile(bundle) as archive:assert archive.testzip() is None


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    codec=MapCodec()
    infos=codec.read('Data/MapInfos.rxdata','infos')
    sets=codec.read('Data/Tilesets.rxdata','tilesets')
    assert infos['39']['parent_id']==38 and '40' not in infos and '41' not in infos
    assert sets[34]['tileset_name']=='NordesteTileset' and sets[24]['tileset_name']=='Inside Geral'
    grids=[make_plaza(sets[34]),make_coliseum(sets[24]),make_market(sets[24])]
    renderer=MapRenderer(sets)
    for g in grids:
        plan=g.plan
        (OUT/f'map-{plan["id"]}-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
        codec.plan(plan,'new_map')
        codec.dump('$new_map',OUT/f'Data/Map{plan["id"]:03d}.rxdata')
        renderer.render(plan).save(OUT/f'map-{plan["id"]}.png')
        renderer.render(plan,markers=True).save(OUT/f'map-{plan["id"]}-events.png')
        print(f'Built map {plan["id"]}: {plan["name"]}, {g.w}x{g.h}, {len(plan["events"])} events',flush=True)
    codec.ruby.evaluate('''
$original_infos=Marshal.load(Marshal.dump($infos))
$infos[39].name='Praca Central'
[ [40,'Coliseu Lunar'], [41,'Mercado Global'] ].each do |id,name|
  raise 'New map ID already registered' if $infos.key?(id)
  info=RPG::MapInfo.new
  info.name,info.parent_id,info.order=name,39,$infos.values.map(&:order).max+1
  $infos[id]=info
end
raise 'Existing map registration changed' unless $original_infos.reject { |id,_| id==39 }.all? { |id,info| Marshal.dump(info)==Marshal.dump($infos[id]) }
'ready'
''')
    codec.dump('$infos',OUT/'Data/MapInfos.rxdata')
    map_metadata(codec,grids)
    packages(codec)
    report=dict(maps=[dict(id=g.plan['id'],name=g.plan['name'],width=g.w,height=g.h,tileset=g.plan['tileset_id'],events=len(g.plan['events']),transfers=g.transfers) for g in grids],
                source_files={name:hashlib.sha256((DEFAULT_GAME/name).read_bytes()).hexdigest() for name in ['Data/Map039.rxdata','Data/MapInfos.rxdata','Data/Tilesets.rxdata','Data/map_metadata.dat','PBS/map_metadata.txt','Data/PluginScripts.rxdata']})
    (OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    report['install_files']={path.relative_to(OUT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in ['Data','PBS','Plugins'] for path in sorted((OUT/folder).rglob('*')) if path.is_file()}
    (OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LOCAL draft only. No game installation or external publication.',flush=True)

if __name__=='__main__':main()
