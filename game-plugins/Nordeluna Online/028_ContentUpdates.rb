# Creator-signed maps, resources and compiled species. No plugins or executables.
module NordelunaOnline
  module ContentUpdates
    BASE = '2ed640fb738bfdce30ecf863841da45f'
    PUBLIC_MODULUS = 'db48a98639249cc352e0d809438cb2e6ee8189affb28acbbcdb29816fc281340a0caa1f0b20712ff11825db355f63448328e7b91ab3a2847fe40a6e3762926e69b83c2924f64b4c45bfb4538d0bcbd2adc030dc9dbedfe11f63cb1b1307366ed1fdba8e34169aedd0eaa30b3abcfc9205e5e6979a2a1c3a8dfb14bf604c675943dfa15657262fe8eb89c7bbb4ba84e95f174812e494b6c8967c7949a3ccbd544f8816c9ac2baa6d4506cbe2128e4fce3394c764c3e92acffa00faba6293124154b9871f5257fc82dd98fcd03a975491a6e2582c6b64beb1a9a17d548ee31ea55a726cdfdcca0bf9a58ca0daefff95def0f06c529ee0508ccf4b70c99f726f199'
    CHUNK = 16_384
    DIRECTORY = '.nordeluna-updates'
    SPECIES_FILES = {'Data/species.dat' => :Species,
                     'Data/species_metrics.dat' => :SpeciesMetrics}.freeze
    DATABASE_FILES = {'Data/types.dat'=>:Type, 'Data/abilities.dat'=>:Ability,
                      'Data/moves.dat'=>:Move, 'Data/items.dat'=>:Item}.merge(SPECIES_FILES).freeze
    INFO = ['3031300d060960864801650304020105000420'].pack('H*')

    # SHA-256 fallback for Android runtimes without the OpenSSL/Digest extension.
    class SHA256
      K = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]
      def initialize
        @h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]
        @buffer=''.b;@length=0
      end
      def r(x,n);((x>>n)|(x<<(32-n)))&0xffffffff;end
      def update(data)
        @length+=data.bytesize;@buffer<<data.b
        while @buffer.bytesize>=64
          w=@buffer.byteslice(0,64).unpack('N16');@buffer=@buffer.byteslice(64..)||''.b
          (16...64).each { |i| x=w[i-15];y=w[i-2];w[i]=(w[i-16]+(r(x,7)^r(x,18)^(x>>3))+w[i-7]+(r(y,17)^r(y,19)^(y>>10)))&0xffffffff }
          a,b,c,d,e,f,g,h=@h
          64.times do |i|
            t1=(h+(r(e,6)^r(e,11)^r(e,25))+((e&f)^((~e)&g))+K[i]+w[i])&0xffffffff
            t2=((r(a,2)^r(a,13)^r(a,22))+((a&b)^(a&c)^(b&c)))&0xffffffff
            h,g,f,e,d,c,b,a=g,f,e,(d+t1)&0xffffffff,c,b,a,(t1+t2)&0xffffffff
          end
          @h=@h.zip([a,b,c,d,e,f,g,h]).map { |x,y| (x+y)&0xffffffff }
        end
        self
      end
      def digest
        bits=@length*8
        update("\x80".b+"\0".b*((55-@length)%64)+[bits>>32,bits&0xffffffff].pack('N2'))
        @h.pack('N8')
      end
      def hexdigest;digest.unpack1('H*');end
    end

    class << self
      def path(name);File.join(DIRECTORY,name);end
      def mkdir(directory)
        return if Dir.exist?(directory)
        parent=File.dirname(directory);mkdir(parent) unless parent==directory || parent=='.'
        Dir.mkdir(directory) unless Dir.exist?(directory)
      end
      def atomic_write(file,data)
        mkdir(File.dirname(file));temporary=file+'.tmp'
        File.binwrite(temporary,data);File.rename(temporary,file)
      end
      def read_json(file);JSON.parse(File.binread(file));end
      def write_json(file,value);atomic_write(file,JSON.dump(value));end
      def installed
        File.file?(path('installed.json')) ? read_json(path('installed.json')) : {'version'=>0,'files'=>[]}
      rescue StandardError
        raise Error,'O registro de atualizacao esta danificado. Envie o relatorio antes de reinstalar.'
      end
      def allowed_path?(value)
        return false unless value.is_a?(String) && value.length<=220 && !value.match?(/[\\:\x00-\x1f]/)
        parts=value.split('/',-1)
        return false if parts.any? { |p| p.empty? || p.start_with?('.') || p.end_with?(' ','.') }
        return true if DATABASE_FILES.key?(value) || value=='Data/regional_dexes.dat'
        return true if %w[Data/MapInfos.rxdata Data/Tilesets.rxdata Data/CommonEvents.rxdata Data/map_metadata.dat Data/map_connections.dat Data/encounters.dat].include?(value)
        return true if value.match?(/\AData\/Map[0-9]{3,6}\.rxdata\z/)
        return parts.length>=3 && value.match?(/\.(png|jpg|jpeg)\z/i) if parts[0]=='Graphics'
        return parts.length>=3 && value.match?(/\.(ogg|mp3|wav|mid|midi)\z/i) if parts[0]=='Audio'
        parts[0]=='Movies' && parts.length>=2 && value.match?(/\.mp4\z/i)
      end
      def sha_file(file)
        digest=SHA256.new
        File.open(file,'rb') do |stream|
          while (data=stream.read(16_384))
            digest.update(data)
            Graphics.frame_reset if defined?(Graphics) && Graphics.respond_to?(:frame_reset)
          end
        end
        digest.hexdigest
      end
      def verify(raw,signature)
        raise Error,'Manifesto invalido.' unless raw.is_a?(String) && raw.bytesize<=150_000 && signature.is_a?(String) && signature.match?(/\A[0-9a-f]{512}\z/)
        digest=INFO+SHA256.new.update(raw).digest
        expected="\0\1".b+"\xff".b*(256-digest.bytesize-3)+"\0".b+digest
        decoded=signature.to_i(16).pow(65_537,PUBLIC_MODULUS.to_i(16)).to_s(16).rjust(512,'0')
        raise Error,'Assinatura do pacote invalida.' unless [decoded].pack('H*')==expected
        data=JSON.parse(raw)
        raise Error,'Este pacote requer outra base do APK.' unless data['base']==BASE
        raise Error,'Versao do pacote invalida.' unless data['version'].is_a?(Integer) && data['version'].between?(1,999_999)
        rows=data['files'];seen={};total=0;compressed=0
        raise Error,'Lista de arquivos invalida.' unless rows.is_a?(Array) && rows.length.between?(1,500)
        rows.each do |row|
          raise Error,'Caminho de atualizacao invalido.' unless row.is_a?(Hash) && allowed_path?(row['path']) && !seen[row['path'].downcase]
          seen[row['path'].downcase]=true
          raise Error,'Hash invalido.' unless %w[sha256 blob].all? { |key| row[key].is_a?(String) && row[key].match?(/\A[0-9a-f]{64}\z/) }
          raise Error,'Arquivo grande demais.' unless %w[size packed_size].all? { |key| row[key].is_a?(Integer) && row[key].between?(1,16_777_216) }
          raise Error,'Base do arquivo invalida.' unless row['base_sha256'].nil? || (row['base_sha256'].is_a?(String) && row['base_sha256'].match?(/\A[0-9a-f]{64}\z/))
          total+=row['size'];compressed+=row['packed_size']
        end
        raise Error,'Pacote grande demais.' if total>67_108_864 || compressed>33_554_432
        data
      end
      def api(data)
        NordelunaOnline.request(NordelunaOnline.server,data.merge('account'=>Identity.ensure_registered))
      end
      def stage_file(row);path("stage/#{row['path']}");end
      def fetch_file(data,row)
        target=stage_file(row)
        return if File.file?(target) && File.size(target)==row['size'] && sha_file(target)==row['sha256']
        temporary=path('download.bin');mkdir(DIRECTORY)
        digest=SHA256.new
        File.open(temporary,'wb') do |stream|
          parts=(row['packed_size']+CHUNK-1)/CHUNK
          parts.times do |part|
            reply=api('action'=>'update_chunk','version'=>data['version'],'blob'=>row['blob'],'part'=>part)
            hex=reply['data'];size=[CHUNK,row['packed_size']-part*CHUNK].min
            raise Error,'Bloco de atualizacao invalido.' unless reply['part']==part && hex.is_a?(String) && hex.length==size*2 && hex.match?(/\A[0-9a-f]+\z/)
            chunk=[hex].pack('H*');stream.write(chunk);digest.update(chunk)
            yield(part+1,parts) if block_given?
            Graphics.update;Input.update
            raise Cancelled,'Download cancelado. O jogo instalado foi preservado.' if Input.trigger?(Input::BACK)
          end
        end
        raise Error,'Download corrompido.' unless digest.hexdigest==row['blob']
        # The signed manifest bounds compressed and uncompressed sizes. Inflate
        # incrementally, checking the limit before writing every output chunk.
        inflater=Zlib::Inflate.new;written=0;mkdir(File.dirname(target))
        begin
          File.open(target+'.tmp','wb') do |output|
            File.open(temporary,'rb') do |input|
              while (block=input.read(256))
                plain=inflater.inflate(block);written+=plain.bytesize
                raise Error,'Arquivo extraido excede o tamanho assinado.' if written>row['size']
                output.write(plain)
              end
            end
          end
          raise Error,'Arquivo extraido incompleto.' unless inflater.finished? && written==row['size'] && sha_file(target+'.tmp')==row['sha256']
          File.rename(target+'.tmp',target)
        ensure
          inflater.close
        end
      end
      def download(reply,data)
        previous=installed
        # Cumulative packs must retain every changed file from prior versions.
        paths=data['files'].map { |r| r['path'] }
        raise Error,'Pacote incompleto em relacao a versao instalada.' unless previous['files'].all? { |r| paths.include?(r['path']) }
        if defined?(Sprite)
          @progress_sprite=Sprite.new;@progress_sprite.z=99_999
          @progress_sprite.bitmap=Bitmap.new([Graphics.width-24,448].min,76)
          @progress_sprite.x=(Graphics.width-@progress_sprite.bitmap.width)/2
          @progress_sprite.y=(Graphics.height-76)/2
          pbSetSystemFont(@progress_sprite.bitmap)
        end
        data['files'].each_with_index do |row,index|
          progress("Arquivo #{index+1}/#{data['files'].length}",0)
          fetch_file(data,row) { |part,total| progress("Arquivo #{index+1}/#{data['files'].length}",part*100/total) }
        end
        write_json(path('pending.json'),reply)
      ensure
        if @progress_sprite
          @progress_sprite.bitmap.dispose;@progress_sprite.dispose;@progress_sprite=nil
        end
      end
      def progress(text,percent)
        return unless @progress_sprite
        bitmap=@progress_sprite.bitmap;bitmap.clear
        bitmap.fill_rect(0,0,bitmap.width,76,Color.new(9,20,33,240))
        bitmap.font.size=18;bitmap.font.color=Color.new(231,246,251)
        bitmap.draw_text(12,3,bitmap.width-24,30,"#{text} / #{percent}%",1)
        bitmap.font.size=14;bitmap.font.color=Color.new(114,224,231)
        bitmap.draw_text(12,31,bitmap.width-24,26,'Baixando atualizacao / Voltar: cancelar',1)
        bitmap.fill_rect(12,65,(bitmap.width-24)*percent/100,3,Color.new(114,224,231))
      end
      def restore_journal(journal)
        journal['files'].each do |row|
          raise Error,'Backup com caminho invalido.' unless allowed_path?(row['path'])
          target=row['path'];backup=path('rollback/'+target)
          if row['existed']
            raise Error,'Backup incompleto.' unless File.file?(backup) && sha_file(backup)==row['sha256']
            atomic_write(target,File.binread(backup))
          elsif File.file?(target)
            File.delete(target)
          end
        end
        write_json(path('installed.json'),journal['previous'])
        reload_species(journal['files'])
      end
      def reload_species(rows)
        return unless defined?(GameData)
        paths=rows.map { |row| row['path'] }
        DATABASE_FILES.each do |file,type|
          next unless paths.include?(file) && GameData.const_defined?(type)
          GameData.const_get(type).load
        end
        if paths.include?('Data/regional_dexes.dat') && defined?($game_temp) && $game_temp && $game_temp.respond_to?(:regional_dexes_data=)
          $game_temp.regional_dexes_data=nil
        end
      end
      def validate_species_files(rows)
        rows.each do |row|
          next unless DATABASE_FILES.key?(row['path'])
          data=Marshal.load(File.binread(stage_file(row)))
          raise Error,'Tabela de Pokemon invalida.' unless data.is_a?(Hash) && !data.empty?
          next unless File.file?(row['path'])
          old=Marshal.load(File.binread(row['path']))
          unless old.is_a?(Hash) && (old.keys-data.keys).empty?
            raise Error,'O pacote remove IDs existentes do banco de dados. Os arquivos e saves foram preservados.'
          end
        end
      end
      def apply_pending
        if File.file?(path('journal.json'))
          journal=read_json(path('journal.json'))
          restore_journal(journal) if journal['phase']=='applying'
          File.delete(path('journal.json'))
        end
        return unless File.file?(path('pending.json'))
        reply=read_json(path('pending.json'));data=verify(reply['manifest'],reply['signature']);previous=installed
        if data['version']<=previous['version']
          File.delete(path('pending.json'));return
        end
        old=previous['files'].to_h { |row| [row['path'],row['sha256']] }
        journal={'phase'=>'prepared','files'=>[],'previous'=>previous}
        # Validate every file and every original before changing anything.
        data['files'].each do |row|
          source=stage_file(row);target=row['path']
          raise Error,'Pacote local incompleto.' unless File.file?(source) && File.size(source)==row['size'] && sha_file(source)==row['sha256']
          existed=File.file?(target);before=existed ? sha_file(target) : nil
          raise Error,'Os arquivos locais nao correspondem a base deste pacote.' unless before==(old[target] || row['base_sha256'])
          atomic_write(path('rollback/'+target),File.binread(target)) if existed
          journal['files']<<{'path'=>target,'existed'=>existed,'sha256'=>before}
        end
        validate_species_files(data['files'])
        journal['phase']='applying';write_json(path('journal.json'),journal)
        begin
          data['files'].each { |row| atomic_write(row['path'],File.binread(stage_file(row))) }
          reload_species(data['files'])
          write_json(path('installed.json'),data)
          journal['phase']='done';write_json(path('journal.json'),journal)
          write_json(path('rollback/info.json'),journal)
          File.delete(path('pending.json'));File.delete(path('journal.json'))
        rescue StandardError
          restore_journal(journal)
          File.delete(path('journal.json')) if File.file?(path('journal.json'))
          raise
        end
        @installed_version=data['version']
      end
      def version;@installed_version ||= installed['version'];end
      def open
        raise Error,'Finalize a batalha ou troca antes de atualizar.' if NordelunaOnline.pending_trade || LunaEconomy.pending || Gifts.pending || $game_temp.in_battle
        reply=api('action'=>'update_manifest','base'=>BASE,'species_updates'=>1,'database_updates'=>1)
        return pbMessage(_INTL('Nenhum pacote novo para esta base do jogo. Conteudo instalado: {1}.',version)) unless reply['manifest']
        data=verify(reply['manifest'],reply['signature'])
        return pbMessage(_INTL('Conteudo do jogo atualizado. Versao: {1}.',version)) if data['version']<=version
        size=data['files'].sum { |r| r['packed_size'] }
        audience=reply['channel']=='testers' ? ' / TESTE RESTRITO' : ''
        choice=OnlineUI.choose('Atualizacao do jogo',["Baixar pacote #{data['version']} (#{(size/1024.0).ceil} KB)#{audience}",'Voltar'],1,data['title'])
        return unless choice==0
        Areas.checked_save!
        MapChannel.suspend if MapChannel.managed?
        download(reply,data)
        pbMessage(_INTL('Download conferido! Feche totalmente o aplicativo e abra novamente para aplicar. Seu save foi preservado.'))
      rescue Cancelled,Error => error
        pbMessage(_INTL('Atualizacao: {1}',error.message))
      rescue StandardError => error
        NordelunaOnline.record_online_error(error,'content_update')
        pbMessage(_INTL('Nao foi possivel concluir a atualizacao. Os arquivos instalados foram preservados.'))
      ensure
        MapChannel.resume if MapChannel.managed? && !File.file?(path('pending.json'))
      end
    end
  end

  module UpdatedMapLoader
    def load_map
      changed=ContentUpdates.version>0 && $PokemonGlobal.nordeluna_content_version!=ContentUpdates.version
      $PokemonGlobal.safesave=true if changed
      result=super
      if changed
        x=[[$game_player.x,0].max,$game_map.width-1].min
        y=[[$game_player.y,0].max,$game_map.height-1].min
        $game_player.moveto(x,y) if x!=$game_player.x || y!=$game_player.y
        $PokemonGlobal.nordeluna_content_version=ContentUpdates.version
      end
      result
    end
  end
  Game.singleton_class.prepend(UpdatedMapLoader)
  module ContentBuildIdentity
    def build
      value=super
      version=ContentUpdates.version
      version>0 ? "#{value}-content#{version}" : value
    end
  end
  singleton_class.prepend(ContentBuildIdentity)
end
class PokemonGlobalMetadata
  attr_accessor :nordeluna_content_version
end

begin
  NordelunaOnline::ContentUpdates.apply_pending
rescue StandardError => error
  # Do not crash or touch the player's save if an interrupted update needs help.
  NordelunaOnline.record_online_error(error,'content_update_boot')
  # Never start with mixed files if automatic rollback could not complete.
  if File.file?(NordelunaOnline::ContentUpdates.path('journal.json'))
    journal=NordelunaOnline::ContentUpdates.read_json(NordelunaOnline::ContentUpdates.path('journal.json'))
    raise if journal['phase']=='applying'
  end
  $nordeluna_update_boot_error=error.message
end
EventHandlers.add(:on_frame_update,:nordeluna_content_update_notice,proc do
  if $nordeluna_update_boot_error && defined?($scene) && $scene.is_a?(Scene_Map) && NordelunaOnline::MapChannel.safe_map?
    message=$nordeluna_update_boot_error;$nordeluna_update_boot_error=nil
    pbMessage(_INTL('A atualizacao nao foi aplicada: {1}',message))
  end
end)
