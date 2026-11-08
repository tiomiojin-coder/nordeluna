class PokemonGlobalMetadata
  attr_accessor :nordeluna_social_status
end

module NordelunaOnline
  module Friends
    LABELS = {"available"=>"Disponivel", "busy"=>"Ocupado", "offline"=>"Offline"}.freeze
    class << self
      def status
        value = $PokemonGlobal && $PokemonGlobal.nordeluna_social_status
        %w[available busy].include?(value) ? value : "available"
      end
      def payload
        @build ||= NordelunaOnline.build
        occupied=!!((@busy || 0)>0 || ($game_temp && $game_temp.in_battle))
        {"status"=>status, "busy"=>occupied, "activity"=>(occupied ? (@activity || "battle") : "available"), "build"=>@build}
      end
      def enabled?; !!@enabled && @url==NordelunaOnline.server; end
      def badge; (@requests || 0)+(@invitations || 0); end
      def choose(title, options, cancel)
        return OnlineUI.choose(title, options, cancel-1) if defined?(OnlineUI)
        pbMessage(title, options, cancel)
      end
      def join_code(mode); @incoming && @incoming["mode"]==mode ? @incoming["code"] : nil; end

      def observe(summary)
        return unless summary.is_a?(Hash) && summary["revision"].is_a?(Integer) && summary["revision"]>=6
        unless summary["request_count"].is_a?(Integer) && summary["request_count"].between?(0,50) &&
               summary["invite_count"].is_a?(Integer) && summary["invite_count"].between?(0,10)
          raise Error, "Resumo social invalido."
        end
        @requests, @invitations = summary.values_at("request_count", "invite_count")
      end

      def snapshot(reply)
        observe(reply)
        %w[friends incoming outgoing invitations].each do |key|
          limit = key=="friends" ? 100 : key=="invitations" ? 10 : 50
          raise Error, "Lista social invalida." unless reply[key].is_a?(Array) && reply[key].length<=limit
          reply[key].each do |row|
            raise Error, "Identidade social invalida." unless row.is_a?(Hash) && row["id"].is_a?(String) &&
              row["id"].match?(/\A[0-9a-f]{32}\z/) && NordelunaOnline.valid_nickname?(row["nickname"])
            if key=="friends"
              raise Error, "Estado de amigo invalido." unless LABELS.key?(row["status"]) && [true,false].include?(row["compatible"])
            elsif key=="invitations"
              raise Error, "Convite invalido." unless row["code"].is_a?(String) && row["code"].match?(/\A[A-Z2-9]{8}\z/) &&
                %w[battle trade].include?(row["mode"]) && row["expires"].is_a?(Integer)
            end
          end
        end
        @data = reply
      end

      def api(action, data={})
        NordelunaOnline.request(@url || NordelunaOnline.server,
          data.merge("action"=>action,"account"=>Identity.ensure_registered))
      end
      def sync
        snapshot(api("social_sync", "presence"=>payload))
        @next_poll = NordelunaOnline.now+10
        @last_error = nil
      end

      def drain
        return if @draining || !@worker
        previous = MapChannel.foreground_request
        MapChannel.foreground_request = true
        acquired = true
        @draining = true
        deadline = NordelunaOnline.now+REQUEST_TIMEOUT
        while @worker && @worker.alive?
          raise ConnectionLost, "Presenca social sem resposta." if NordelunaOnline.now>=deadline
          NordelunaOnline.frame
        end
        collect
      rescue StandardError => error
        @worker.cancel if @worker
        @worker = nil
        @last_error = error.message
        @next_poll = NordelunaOnline.now+15
      ensure
        if acquired
          @draining = false
          MapChannel.foreground_request = previous
        end
      end

      def collect
        return unless @worker && !@worker.alive?
        ticket = @worker
        @worker = nil
        result = ticket.value
        raw = result.is_a?(Hash) && (result[:body] || result["body"])
        raise ConnectionLost, "Resposta social invalida." unless raw.is_a?(String) && raw.bytesize<=MAX_RESPONSE
        reply = JSON.parse(raw)
        raise Error, reply.is_a?(Hash) ? reply["error"].to_s : "Resposta social invalida." unless reply.is_a?(Hash) && reply["ok"]==true
        snapshot(reply)
      ensure
        ticket.cancel if ticket
      end

      def update
        return if @draining || @updating
        @updating = true
        begin
          collect if @worker && !@worker.alive?
          if @worker && NordelunaOnline.now>=@worker_deadline
            @worker.cancel;@worker=nil
            @next_poll=NordelunaOnline.now+15
          end
          return unless enabled? && (@busy || 0)==0 && !@worker
          return if MapChannel.managed? || !$scene.is_a?(Scene_Map) || !$game_temp ||
            $game_temp.in_battle ||
            ((!@modal) && ($game_temp.in_menu || $game_temp.message_window_showing || pbMapInterpreterRunning?))
          return if NordelunaOnline.now<(@next_poll || 0) || !Transport.idle?
          @next_poll=NordelunaOnline.now+10
          @worker=Transport.start(@url, {"action"=>"social_sync","account"=>@account,"presence"=>payload})
          @worker_deadline=NordelunaOnline.now+REQUEST_TIMEOUT
        rescue StandardError => error
          @last_error=error.message
          @next_poll=NordelunaOnline.now+15
          @worker.cancel if @worker
          @worker=nil
        ensure
          @updating=false
        end
      end

      def after_request(url, request, reply)
        if @incoming && request["action"]=="join" && request["code"]==@incoming["code"]
          @joined=true
        end
        return unless @target && request["action"]=="create"
        begin
          api("social_invite", "target"=>@target["id"],"code"=>reply.fetch("code"),
            "mode"=>request["mode"],"room_token"=>reply.fetch("token"))
          pbMessage(_INTL("Convite enviado para {1}. Ele expira em dois minutos. Seu amigo ainda precisa aceitar e escolher a equipe ou oferta.", @target["nickname"]))
        rescue StandardError
          NordelunaOnline.request(url,"action"=>"cancel","code"=>reply["code"],"token"=>reply["token"]) rescue nil
          raise
        end
      end

      def busy(activity="busy")
        previous_activity=@activity
        @activity=activity
        @busy=(@busy || 0)+1
        begin
          sync if enabled?
        rescue StandardError => error
          @last_error=error.message
        end
        yield
      ensure
        @busy=[(@busy || 1)-1,0].max
        @activity=previous_activity
        begin
          sync if enabled?
        rescue StandardError => error
          @last_error=error.message
        end
      end

      def send_invitation(friend, mode)
        raise Error, "Este amigo esta offline ou ocupado." unless friend["status"]=="available"
        raise VersionMismatch, "Atualize os dois jogos para a mesma versao." unless friend["compatible"]
        @target=friend
        NordelunaOnline.connect(mode,false)
      ensure
        @target=nil
      end

      def accept_invitation(invitation)
        accepted=api("social_invite_reply","invitation"=>invitation["id"],"accept"=>true)
        raise VersionMismatch, "As versoes do jogo sao diferentes." unless accepted["build"]==NordelunaOnline.build
        raise Error, "Convite retornado invalido." unless accepted["code"]==invitation["code"] && accepted["mode"]==invitation["mode"]
        @incoming=accepted;@joined=false
        NordelunaOnline.connect(accepted["mode"],true)
      ensure
        if accepted && !@joined
          api("social_invite_reply","invitation"=>invitation["id"],"accept"=>false) rescue nil
        end
        @incoming=nil;@joined=false
      end

      def open
        drain
        @modal=true
        health=NordelunaOnline.test_connection(false)
        raise VersionMismatch, "Amigos e convites precisam do servidor revisao 6. Atualize o servidor para usar esta opcao." unless health["revision"].to_i>=6
        return unless NordelunaOnline.valid_nickname?($PokemonGlobal.nordeluna_online_nickname) || NordelunaOnline.configure_nickname
        @url=NordelunaOnline.server;@build=NordelunaOnline.build
        @account=Identity.ensure_registered;@enabled=true
        sync
        loop do
          n=choose(_INTL("Amigos e convites\nSeu status: {1}", LABELS[status]),
            [_INTL("Meus amigos ({1})",@data["friends"].length),_INTL("Adicionar por nick"),
             _INTL("Pedidos de amizade ({1})",@requests),_INTL("Convites ({1})",@invitations),
             _INTL("Meu status"),_INTL("Atualizar"),_INTL("Voltar")],7)
          case n
          when 0 then list_friends
          when 1
            nick=pbMessageFreeText(_INTL("Nick exato do treinador:"),"",false,16).strip
            snapshot(api("social_add","nickname"=>nick)) unless nick.empty?
          when 2 then requests_menu
          when 3 then invitations_menu
          when 4
            value=choose(_INTL("Como seus amigos devem ver voce?"),[_INTL("Disponivel"),_INTL("Ocupado"),_INTL("Voltar")],3)
            if [0,1].include?(value)
              old=$PokemonGlobal.nordeluna_social_status
              $PokemonGlobal.nordeluna_social_status=%w[available busy][value]
              begin
                Areas.checked_save!
              rescue StandardError
                $PokemonGlobal.nordeluna_social_status=old
                raise
              end
            end
          when 5 then nil
          else break
          end
          sync
        end
      rescue Error => error
        pbMessage(_INTL("Amigos: {1}",error.message))
      rescue StandardError => error
        NordelunaOnline.record_online_error(error,"friends_menu")
        pbMessage(_INTL("Nao foi possivel abrir esta opcao. O diagnostico foi registrado."))
      ensure
        @modal=false
      end

      def reset
        CosmeticBadges.reset if defined?(CosmeticBadges)
        LunaEconomy.reset_cache if defined?(LunaEconomy)
        @worker.cancel if @worker
        @worker=@account=@data=@url=@build=@incoming=@target=nil
        @enabled=@modal=@draining=@updating=false
        @requests=@invitations=@busy=0
      end

      def list_friends
        rows=@data["friends"]
        return pbMessage(_INTL("Sua lista esta vazia. Envie um pedido pelo nick.")) if rows.empty?
        n=choose(_INTL("Meus amigos:"),rows.map { |row| "#{row['nickname']} - #{LABELS[row['status']]}" }+[_INTL("Voltar")],rows.length+1)
        return unless n>=0 && n<rows.length
        friend=rows[n]
        action=choose(_INTL("{1} - {2}",friend["nickname"],LABELS[friend["status"]]),
          [_INTL("Convidar para batalha"),_INTL("Convidar para troca"),_INTL("Remover amizade"),_INTL("Voltar")],4)
        if [0,1].include?(action)
          send_invitation(friend,%w[battle trade][action])
        elsif action==2 && pbConfirmMessage(_INTL("Remover a amizade com {1}?",friend["nickname"]))
          snapshot(api("social_remove","target"=>friend["id"]))
        end
      end

      def requests_menu
        rows=@data["incoming"].map { |row| [row,true] }+@data["outgoing"].map { |row| [row,false] }
        return pbMessage(_INTL("Nenhum pedido pendente.")) if rows.empty?
        n=choose(_INTL("Pedidos de amizade:"),rows.map { |row,incoming| "#{incoming ? 'Recebido' : 'Enviado'}: #{row['nickname']}" }+[_INTL("Voltar")],rows.length+1)
        return unless n>=0 && n<rows.length
        row,incoming=rows[n]
        if incoming
          answer=choose(_INTL("Pedido de {1}",row["nickname"]),[_INTL("Aceitar"),_INTL("Recusar"),_INTL("Voltar")],3)
          snapshot(api("social_friend_reply","target"=>row["id"],"accept"=>answer==0)) if [0,1].include?(answer)
        elsif pbConfirmMessage(_INTL("Cancelar pedido enviado a {1}?",row["nickname"]))
          snapshot(api("social_request_cancel","target"=>row["id"]))
        end
      end

      def invitations_menu
        rows=@data["invitations"]
        return pbMessage(_INTL("Nenhum convite pendente.")) if rows.empty?
        n=choose(_INTL("Convites recebidos:"),rows.map { |row| "#{row['nickname']} - #{row['mode']=='battle' ? 'Batalha' : 'Troca'}" }+[_INTL("Voltar")],rows.length+1)
        return unless n>=0 && n<rows.length
        invitation=rows[n]
        answer=choose(_INTL("Convite de {1}. Aceitar abre as confirmacoes normais da sala.",invitation["nickname"]),
          [_INTL("Aceitar"),_INTL("Recusar"),_INTL("Voltar")],3)
        if answer==0
          accept_invitation(invitation)
        elsif answer==1
          api("social_invite_reply","invitation"=>invitation["id"],"accept"=>false)
        end
      end
    end
  end

  module FriendsRequests
    def request(url,data)
      Friends.drain
      reply=super
      Friends.after_request(url,data,reply)
      reply
    end
    def connect(mode,join)
      Friends.busy(mode) { super }
    end
  end
  singleton_class.prepend(FriendsRequests)

  module FriendsMapRequests
    def start_room_request(data,operation)
      Friends.drain
      data=data.merge("social"=>Friends.payload) if Friends.enabled?
      super(data,operation)
    end
  end
  MapChannel.singleton_class.prepend(FriendsMapRequests)

  module FriendsFrames
    def update(*args)
      result=super
      Friends.update
      result
    end
  end
  Graphics.singleton_class.prepend(FriendsFrames)

  module FriendsGameReset
    def load_map(*args)
      Friends.reset
      super
    end
    def start_new(*args)
      Friends.reset
      super
    end
  end
  Game.singleton_class.prepend(FriendsGameReset)
end

MenuHandlers.add(:pause_menu,:nordeluna_friends,{
  "name"=>proc { n=NordelunaOnline::Friends.badge; n>0 ? _INTL("Amigos e convites ({1})",n) : _INTL("Amigos e convites") },
  "order"=>46,"condition"=>proc { $game_temp && !$game_temp.in_battle },
  "effect"=>proc { |menu| next NordelunaOnline.run_pause_action(menu) { NordelunaOnline::Friends.open } }
})
