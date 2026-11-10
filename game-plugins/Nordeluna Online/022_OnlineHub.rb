module NordelunaOnline
  # One visual language and one input loop for touch, keyboard and controllers.
  module OnlineUI
    BACKGROUND = [9,20,33,248].freeze
    ACCENT = [101,222,235].freeze
    TEXT = [232,240,248].freeze
    MUTED = [156,177,195].freeze
    STATES = {"available"=>["Disponivel",[100,218,171]], "busy"=>["Ocupado",[244,190,102]],
              "battle"=>["Em batalha",[238,137,134]], "trade"=>["Em troca",[169,164,240]]}.freeze
    class << self
      def modal?; (@depth || 0)>0; end
      def color(key); Color.new(*const_get(key)); end
      def asset(name,width,height)
        @art ||= {}
        return @art[name] if @art.key?(name)
        @art[name]=nil
        path="Plugins/Nordeluna Online/assets/#{name}.png"
        return unless File.file?(path)
        source=Bitmap.new(path)
        target=Bitmap.new(width,height)
        target.stretch_blt(Rect.new(0,0,width,height),source,Rect.new(0,0,source.width,source.height))
        @art[name]=target
      rescue StandardError
        target.dispose if target && !target.disposed?
        nil
      ensure
        source.dispose if source && !source.disposed?
      end
      def draw_background(bitmap,width,height)
        art=asset('menu-background',512,384)
        if art
          bitmap.stretch_blt(Rect.new(0,0,width,height),art,Rect.new(0,0,512,384))
        else
          ChatPanel.box(bitmap,0,0,width,height,color(:BACKGROUND))
        end
      end
      def draw_coin(bitmap,x,y)
        art=asset('luna-coin',32,32)
        bitmap.blt(x,y,art,Rect.new(0,0,32,32)) if art
      end
      def bounds(count=nil)
        width,height=[424,Graphics.width-24].min,[344,Graphics.height-24].min
        height=[height,count*34+110].min if count
        [(Graphics.width-width)/2,(Graphics.height-height)/2,width,height]
      end
      def pointer
        return unless Input.const_defined?(:MOUSELEFT) && Input.respond_to?(:mouse_x) && Input.respond_to?(:mouse_y)
        x,y=Input.mouse_x,Input.mouse_y
        [x,y] if x.is_a?(Numeric) && y.is_a?(Numeric)
      end
      def pointer_down?; Input.const_defined?(:MOUSELEFT) && Input.press?(Input::MOUSELEFT); end
      def pointer_start?; Input.const_defined?(:MOUSELEFT) && Input.trigger?(Input::MOUSELEFT); end

      def choose(title, options, cancel=options.length-1, subtitle=nil)
        raise Error,"Menu online vazio." if options.empty?
        previous_menu=$game_temp.in_menu
        previous_scene=$scene
        @depth=(@depth || 0)+1
        entered=true
        $game_temp.in_menu=true
        ChatPanel.hide
        left,top,width,height=bounds(options.length)
        screen=ChatPanel.create_sprite(width,height)
        screen.x,screen.y=left,top
        screen.z=96000+@depth
        selected=offset=0
        row_height=34
        count=[(height-110)/row_height,1].max
        maximum=[options.length-count,0].max
        closing=[width-43,9,32,32]
        heading,*details=title.to_s.split("\n")
        subtitle ||= details.join(" / ")
        signature=nil
        touch=nil
        loop do
          Graphics.update
          Input.update
          return cancel if $scene!=previous_scene
          point=pointer
          local=point && [point[0]-left,point[1]-top]
          if pointer_start? && local
            touch={origin:local,last:local,offset:offset,dragged:false}
          end
          if touch && local
            delta=local[1]-touch[:origin][1]
            touch[:dragged]=true if delta.abs>8 || (local[0]-touch[:origin][0]).abs>8
            if touch[:dragged]
              offset=[[touch[:offset]-(delta/row_height.to_f).round,0].max,maximum].min
              selected=[[selected,offset].max,offset+count-1].min
            end
            touch[:last]=local
          end
          if touch && !pointer_down?
            if !touch[:dragged] && local && ChatPanel.inside?(local,closing)
              return cancel
            elsif !touch[:dragged] && local && local[0].between?(14,width-15) && local[1]>=72
              index=offset+((local[1]-72)/row_height).floor
              return index if index<options.length && local[1]<72+count*row_height
            end
            touch=nil
          end
          return cancel if Input.trigger?(Input::BACK)
          if Input.trigger?(Input::UP)
            selected=(selected-1)%options.length
          elsif Input.trigger?(Input::DOWN)
            selected=(selected+1)%options.length
          elsif Input.trigger?(Input::USE)
            return selected
          end
          offset=selected if selected<offset
          offset=selected-count+1 if selected>=offset+count
          state=[selected,offset,subtitle]
          if signature!=state
            bitmap=screen.bitmap
            bitmap.clear
            draw_background(bitmap,width,height)
            bitmap.fill_rect(8,0,width-16,2,color(:ACCENT))
            bitmap.font.size=20
            ChatPanel.text(bitmap,ChatPanel.fit(bitmap,heading,width-77),14,8,width-77,20,color(:ACCENT))
            bitmap.font.size=13
            subtitle_width=width-145
            ChatPanel.text(bitmap,ChatPanel.fit(bitmap,subtitle.to_s,subtitle_width),14,36,subtitle_width,13,color(:MUTED))
            draw_coin(bitmap,width-125,31)
            balance=defined?(LunaEconomy) && LunaEconomy.snapshot ? LunaEconomy.snapshot['balance'] : '--'
            ChatPanel.text(bitmap,"#{balance} LC",width-89,36,80,13,Color.new(247,214,131))
            ChatPanel.button(bitmap,"X",closing)
            options.slice(offset,count).each_with_index do |label,i|
              y=72+i*row_height
              active=selected==offset+i
              ChatPanel.box(bitmap,14,y,width-28,30,Color.new(*(active ? [30,69,88] : [18,35,51])))
              bitmap.fill_rect(14,y+4,2,22,color(:ACCENT)) if active
              bitmap.font.size=16
              ChatPanel.text(bitmap,ChatPanel.fit(bitmap,label,width-62),25,y+3,width-62,16,color(:TEXT))
              ChatPanel.text(bitmap,">",width-34,y+3,20,16,color(:MUTED))
            end
            if maximum>0
              track=count*row_height-5
              bitmap.fill_rect(width-7,74,2,track,Color.new(38,59,75))
              thumb=[track*count/options.length,12].max
              bitmap.fill_rect(width-7,74+(track-thumb)*offset/maximum,2,thumb,color(:ACCENT))
            end
            hint=maximum>0 ? "Arraste para rolar / toque para escolher" : "Toque para escolher / voltar para fechar"
            hint="Setinhas: escolher / Confirmar: abrir / Voltar: sair"
            ChatPanel.text(bitmap,hint,14,height-28,width-28,11,color(:MUTED))
            signature=state
          end
        end
      ensure
        if entered
          ChatPanel.dispose_sprite(screen)
          $game_temp.in_menu=previous_menu if $game_temp
          @depth=[(@depth || 1)-1,0].max
          Input.update
        end
      end

      def nameplate(bitmap, name, state, badge='')
        label,rgb=STATES.fetch(state,STATES["available"])
        bitmap.clear
        bitmap.font.size=16
        decorated=defined?(CosmeticBadges) && CosmeticBadges.show? && CosmeticBadges::IDS.include?(badge)
        name=ChatPanel.fit(bitmap,NordelunaOnline.safe_label(name),decorated ? 232 : 254)
        text_width=bitmap.text_size(name).width
        plate_width=[[text_width+(decorated ? 24 : 8),80].max,260].min
        if decorated
          x=(decorated ? 141 : 131)-text_width/2-17
          c=badge=='community_50' ? Color.new(249,211,117) : Color.new(114,224,231)
          bitmap.fill_rect(x+3,9,3,13,c)
          bitmap.fill_rect(x,13,9,5,c)
          bitmap.fill_rect(x+1,11,7,9,c)
        end
        # Transparent nameplates: a small outline stays readable over every tile.
        bitmap.font.color=Color.new(*NICK_OUTLINE)
        [[-1,0],[1,0],[0,-1],[0,1]].each do |dx,dy|
          bitmap.draw_text((decorated ? 20 : 0)+dx,2+dy,decorated ? 242 : 262,26,name,1)
        end
        bitmap.font.color=Color.new(*NICK_COLOR)
        bitmap.draw_text(decorated ? 20 : 0,2,decorated ? 242 : 262,26,name,1)
        bitmap.font.size=12
        bitmap.font.color=Color.new(12,21,33)
        [[-1,0],[1,0],[0,-1],[0,1]].each { |dx,dy| bitmap.draw_text(dx,21+dy,262,22,label,1) }
        bitmap.font.color=Color.new(*rgb)
        bitmap.draw_text(0,21,262,22,label,1)
        plate_width
      end
    end
  end

  module SocialHub
    class << self
      def open
        return unless $player && $PokemonGlobal
        initial_map=$game_map&.map_id
        loop do
          if NordelunaOnline.pending_trade
            NordelunaOnline.recover_trade
            return if NordelunaOnline.pending_trade
          end
          badge=Friends.badge
          choice=OnlineUI.home_cards
          result=case choice
          when 0 then MapChannel.connect("PRACA") ? :sent : nil
          when 1 then Friends.open
          when 2 then Gifts.open
          when 3 then LunaEconomy.open
          when 4 then nearby
          when 5 then ChatPanel.open_chat
          when 6 then matches
          when 7 then emotes
          when 8 then profile
          when 9 then connection
          when 10 then ContentUpdates.open
          when 12 then LunaEconomy.shop
          else return
          end
          return :sent if result==:sent || initial_map!=$game_map&.map_id
        end
      rescue Error => error
        pbMessage(_INTL("Online: {1}",error.message))
      rescue StandardError => error
        NordelunaOnline.record_online_error(error,"online_hub")
        pbMessage(_INTL("Nao foi possivel abrir esta opcao. O diagnostico foi registrado."))
      end

      def more
        actions=[2,3,4,7,8,10,11]
        n=OnlineUI.choose('Mais do Online',['Presentes','Missoes e comunidade','Jogadores proximos','Emotes','Meu perfil','Atualizacoes','Voltar'],6)
        actions[n]
      end

      def matches
        action=OnlineUI.choose("Batalhas e trocas",["Procurar batalha","Batalha: criar sala","Batalha: entrar por codigo",
          "Troca: criar sala","Troca: entrar por codigo","Recuperar troca pendente","Voltar"],6,
          "Equipes e ofertas sempre passam por confirmacao")
        return Matchmaking.search if action==0
        return NordelunaOnline.recover_trade if action==5
        action-=1
        NordelunaOnline.connect(action<2 ? "battle" : "trade",action.odd?) if action.between?(0,3)
      end

      def profile
        case OnlineUI.choose("Meu perfil",["Alterar nick online","Alterar disponibilidade","Emblemas cosmeticos","Voltar"],3,NordelunaOnline.nickname)
        when 0 then NordelunaOnline.configure_nickname
        when 1
          answer=OnlineUI.choose("Disponibilidade",["Disponivel","Ocupado","Voltar"],2,"Salvo no seu progresso")
          return if answer==2
          previous=$PokemonGlobal.nordeluna_social_status
          begin
            $PokemonGlobal.nordeluna_social_status=%w[available busy][answer]
            Areas.checked_save!
          rescue StandardError
            $PokemonGlobal.nordeluna_social_status=previous
            raise
          end
          Friends.sync if Friends.enabled?
        when 2 then CosmeticBadges.menu
        end
      end

      def connection
        case OnlineUI.choose("Conexao",["Salas privadas","Testar conexao","Diagnostico","Alterar servidor","Sair da praca","Voltar"],5,MapChannel.connection_label)
        when 0 then NordelunaOnline.room_menu
        when 1 then NordelunaOnline.test_connection(true)
        when 2 then ChatPanel.modal_loop(:diagnostic)
        when 3 then NordelunaOnline.configure_server
        when 4
          MapChannel.disconnect
          :sent
        end
      end

      def emotes
        n=OnlineUI.choose("Emotes",["Acenar","Comemorar","Chamar para batalha","Voltar"],3,"Visiveis aos jogadores desta sala")
        if n.between?(0,2)
          MapChannel.send_emote(%w[wave celebrate battle][n])
          :sent
        end
      end

      def nearby
        people=Ghosts.rows.values.sort_by { |v| [(v.data['x']-$game_player.x).abs+(v.data['y']-$game_player.y).abs,v.data['name']] }
        return pbMessage(_INTL("Nenhum treinador nesta area. Entre na praca para encontrar jogadores.")) if people.empty?
        n=OnlineUI.choose("Jogadores proximos",people.map { |v| v.data['name'] }+["Voltar"],people.length,"Toque em um nome para abrir o cartao")
        peer_card(people[n].data) if n>=0 && n<people.length
      end

      def peer_card(peer)
        return if @opening
        @opening=true
        acquired=true
        Friends.activate
        Friends.sync
        known=Friends.instance_variable_get(:@data)
        friend=known['friends'].any? { |row| row['id']==peer['account_id'] }
        state=peer['status'] || 'available'
        choice=OnlineUI.choose(peer['name'],[friend ? "Amizade confirmada" : "Adicionar amigo",
          "Convidar para batalha","Convidar para troca","Voltar"],3,
          "#{OnlineUI::STATES.fetch(state,OnlineUI::STATES['available'])[0]} / Sala #{MapChannel.room_name}")
        if choice==0 && !friend
          Friends.snapshot(Friends.api('social_add','nickname'=>peer['name']))
          pbMessage(_INTL("Pedido enviado a {1}. A amizade depende da confirmacao dele.",peer['name']))
        elsif [1,2].include?(choice)
          Friends.send_invitation({'id'=>peer['account_id'],'nickname'=>peer['name'],
            'status'=>state=='available' ? 'available' : 'busy','compatible'=>true},choice==1 ? 'battle' : 'trade')
        end
      rescue Error => error
        pbMessage(_INTL("Treinador: {1}",error.message))
      ensure
        @opening=false if acquired
      end
    end
  end

  module FriendsActivation
    def activate
      @url=NordelunaOnline.server
      @build=NordelunaOnline.build
      @account=Identity.ensure_registered
      @enabled=true
      @next_poll=0
    end
  end
  Friends.singleton_class.prepend(FriendsActivation)

  module HubChannel
    def accept_join(reply)
      result=super
      Friends.activate if reply['revision'].to_i>=6
      result
    end

    # Keep the avatar/status alive while the battle owns foreground requests.
    # Only use an idle transport; never start a second request alongside it.
    def keepalive
      return super unless @suspended
      acquired=false
      return unless managed? && active? && @desired && Areas.active?
      return if @worker || @updating || @keeping_alive || foreground_request || !Transport.idle?
      return if NordelunaOnline.now<(@next_keepalive || 0)
      @keeping_alive=acquired=true
      @next_keepalive=NordelunaOnline.now+3
      start_room_request({'action'=>'map_ping','token'=>@token,'after'=>@chat_cursor || 0,'chat_epoch'=>@chat_epoch},:ping)
    rescue StandardError => error
      connection_failed(error)
    ensure
      @keeping_alive=false if acquired
    end

    def connection_failed(error)
      if @suspended
        # A failed presence heartbeat must not transfer maps during a battle.
        RoomChannel.instance_method(:connection_failed).bind(self).call(error)
      else
        super
      end
    end
  end
  MapChannel.singleton_class.prepend(HubChannel)

  module HubEntry
    def open; SocialHub.open; end
  end
  singleton_class.prepend(HubEntry)
end

%i[nordeluna_map_emotes nordeluna_friends nordeluna_room_chat nordeluna_diagnostics nordeluna_nearby_players].each do |key|
  MenuHandlers.remove(:pause_menu,key) if MenuHandlers.respond_to?(:remove)
end
MenuHandlers.add(:pause_menu,:nordeluna_online,{
  'name'=>proc { n=NordelunaOnline::Friends.badge; n+=1 if defined?(NordelunaOnline::Gifts) && NordelunaOnline::Gifts.pending; n>0 ? _INTL('Online ({1})',n) : _INTL('Online') },
  'order'=>45,'condition'=>proc { $game_temp && !$game_temp.in_battle },
  'effect'=>proc { |menu| next NordelunaOnline.run_pause_action(menu) { NordelunaOnline.open } }
})
