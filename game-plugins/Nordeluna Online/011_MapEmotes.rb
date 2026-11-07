module NordelunaOnline
  module MapChannel
    EMOTES = { "wave" => "Acenou!", "celebrate" => "Comemorou!", "battle" => "Vamos batalhar?" }
    COOLDOWN = 3.0
    class << self
      attr_reader :error

      def active?; !!@token; end

      def safe_map?
        defined?(Scene_Map) && $scene.is_a?(Scene_Map) && $game_temp &&
          !$game_temp.in_battle && !$game_temp.in_menu && !$game_temp.message_window_showing &&
          $game_map && !$game_map.interpreter.running? && $game_player
      end

      def position
        { "map" => $game_map.map_id, "x" => $game_player.x, "y" => $game_player.y }
      end

      def connect
        return if active?
        return unless NordelunaOnline.valid_nickname?($PokemonGlobal.nordeluna_online_nickname) || NordelunaOnline.configure_nickname
        health = NordelunaOnline.test_connection(false)
        raise VersionMismatch, "Emotes precisam do servidor revisao 3. Atualize o servidor primeiro." if health["revision"] < 3
        @url = NordelunaOnline.server
        reply = NordelunaOnline.request(@url, "action" => "map_join", "profile" => NordelunaOnline.profile, "build" => NordelunaOnline.build)
        @token = reply.fetch("token")
        @id = reply.fetch("id")
        @error = nil
        @next_poll = 0
        @last_emote = -COOLDOWN
        @bubbles = {}
        @sequences = {}
      end

      # A foreground request never races the map worker. Only transport runs in
      # the worker; all Graphics/Input/JSON and sprite work stays on the main thread.
      def drain
        return unless @worker
        while @worker.alive?
          check_timeout
          Graphics.update
          Input.update
        end
        collect
      rescue StandardError => error
        @error = error.message
        @token = nil
        @queued = @sent_emote = nil
        dispose_bubbles
        # A failed social channel must not prevent a foreground PvP/trade request.
      end

      def check_timeout
        return unless @worker && @worker.alive? && NordelunaOnline.now >= @worker_deadline
        @worker.kill
        @worker = nil
        @token = nil
        @sent_emote = nil
        @error = "Canal de mapa sem resposta. Entre novamente quando a conexao voltar."
        raise Error, @error
      end

      def disconnect
        drain
        token = @token
        @token = nil
        @queued = nil
        dispose_bubbles
        NordelunaOnline.request(@url, "action" => "map_leave", "token" => token) if token
      rescue StandardError
        # Server TTL also removes presence after a lost connection.
        @token = nil
      end

      def send_emote(id)
        raise Error, "Entre no canal de mapa primeiro." unless active?
        raise Error, "Emote invalido." unless EMOTES.key?(id)
        raise Error, "Espere 3 segundos entre emotes." if @queued || @sent_emote || NordelunaOnline.now - @last_emote < COOLDOWN
        @queued = id
        @next_poll = 0
      end

      def collect
        return unless @worker && !@worker.alive?
        result = @worker.value
        @worker = nil
        raise Error, "Canal de mapa sem resposta." unless result.is_a?(Hash)
        raw = result[:body] || result["body"]
        raise Error, "Resposta de mapa invalida." unless raw.is_a?(String) && raw.bytesize <= MAX_RESPONSE
        reply = JSON.parse(raw)
        raise Error, reply.is_a?(Hash) ? reply["error"].to_s : "Resposta de mapa invalida." unless reply.is_a?(Hash) && reply["ok"] == true
        peers = reply["peers"]
        raise Error, "Lista de jogadores invalida." unless peers.is_a?(Array) && peers.length <= 40
        # Ignore an old-map response after a transition.
        if @sent_position["map"] == $game_map.map_id
          peers.each { |peer| receive(peer) }
          if @sent_emote
            show_bubble(@id, NordelunaOnline.nickname, @sent_emote, @sent_position["x"], @sent_position["y"])
            @last_emote = NordelunaOnline.now
          end
        end
        @sent_emote = nil
      end

      def receive(peer)
        return unless peer.is_a?(Hash) && peer["id"].is_a?(String) && peer["sequence"].is_a?(Integer)
        return unless EMOTES.key?(peer["emote"]) && peer["x"].is_a?(Integer) && peer["y"].is_a?(Integer)
        return if @sequences[peer["id"]] == peer["sequence"]
        @sequences[peer["id"]] = peer["sequence"]
        @sequences.shift while @sequences.length > 500
        show_bubble(peer["id"], NordelunaOnline.safe_label(peer["name"]), peer["emote"], peer["x"], peer["y"])
      end

      def show_bubble(id, name, emote, x, y)
        @bubbles ||= {}
        old = @bubbles.delete(id)
        dispose_bubble(old) if old
        sprite = Sprite.new
        sprite.bitmap = Bitmap.new(260, 54)
        sprite.bitmap.fill_rect(0, 0, 260, 54, Color.new(15, 29, 51, 225))
        sprite.bitmap.font.size = 17
        sprite.bitmap.font.color = Color.new(240, 248, 255)
        sprite.bitmap.draw_text(6, 1, 248, 24, NordelunaOnline.safe_label(name), 1)
        sprite.bitmap.font.color = Color.new(100, 220, 245)
        sprite.bitmap.draw_text(6, 25, 248, 24, _INTL(EMOTES.fetch(emote)), 1)
        sprite.z = 90000
        @bubbles[id] = { :sprite => sprite, :x => x, :y => y, :map => $game_map.map_id, :until => NordelunaOnline.now + 4 }
      end

      def dispose_bubble(bubble)
        sprite = bubble[:sprite]
        sprite.bitmap.dispose if sprite.bitmap && !sprite.bitmap.disposed?
        sprite.dispose unless sprite.disposed?
      end

      def dispose_bubbles
        (@bubbles || {}).each_value { |bubble| dispose_bubble(bubble) }
        @bubbles = {}
      end

      def update_bubbles(visible)
        (@bubbles || {}).keys.each do |id|
          bubble = @bubbles[id]
          if bubble[:map] != $game_map.map_id || NordelunaOnline.now >= bubble[:until]
            dispose_bubble(@bubbles.delete(id))
            next
          end
          sprite = bubble[:sprite]
          # RPG Maker map display offsets use 1/128 tile units.
          sprite.x = ((bubble[:x] + 0.5) * 32 - $game_map.display_x / 4.0 - 130).round
          sprite.y = (bubble[:y] * 32 - $game_map.display_y / 4.0 - 66).round
          sprite.visible = visible && sprite.x > -260 && sprite.x < Graphics.width && sprite.y > -54 && sprite.y < Graphics.height
          sprite.x = [[sprite.x, 0].max, [Graphics.width - 260, 0].max].min
          sprite.y = [[sprite.y, 0].max, [Graphics.height - 54, 0].max].min
        end
      end

      def update
        return if @updating
        @updating = true
        begin
          check_timeout
          collect if @worker && !@worker.alive?
          return unless $game_map
          safe = safe_map?
          update_bubbles(safe)
          return unless active? && safe && !@worker && NordelunaOnline.now >= (@next_poll || 0)
          @sent_position = position
          @sent_emote = @queued
          @queued = nil
          body = JSON.dump({ "protocol" => PROTOCOL, "action" => "map_update", "token" => @token,
            "state" => @sent_position, "emote" => @sent_emote })
          endpoint = @url + "/api"
          @worker_deadline = NordelunaOnline.now + REQUEST_TIMEOUT
          @worker = Thread.new do
            begin
              HTTPLite.post_body(endpoint, body, "application/json", { "Accept" => "application/json" })
            rescue StandardError
              nil
            end
          end
          @next_poll = NordelunaOnline.now + 1.0
        rescue StandardError => error
          @error = error.message
          @token = nil
          @queued = @sent_emote = nil
          dispose_bubbles
        ensure
          @updating = false
        end
      end
    end
  end

  module MapNetworkGate
    def request(url, data)
      MapChannel.drain
      super
    end
    def configure_nickname
      MapChannel.disconnect
      super
    end
    def configure_server
      MapChannel.disconnect
      super
    end
  end
  singleton_class.prepend(MapNetworkGate)

  def self.map_emotes_menu
    loop do
      label = MapChannel.active? ? _INTL("Canal conectado - somente jogadores deste mapa e versao.") : _INTL("Canal desconectado")
      label += "\n" + safe_label(MapChannel.error) if MapChannel.error
      choice = pbMessage(label, [_INTL("Entrar no canal"), _INTL("Acenar"), _INTL("Comemorar"),
        _INTL("Chamar para batalha"), _INTL("Sair do canal"), _INTL("Voltar")], 6)
      case choice
      when 0 then MapChannel.connect
      when 1, 2, 3
        MapChannel.send_emote(%w[wave celebrate battle][choice - 1])
        return
      when 4 then MapChannel.disconnect
      else return
      end
    end
  rescue Error => error
    pbMessage(_INTL("Emotes: {1}", error.message))
  end
end

EventHandlers.add(:on_frame_update, :nordeluna_map_emotes, proc { NordelunaOnline::MapChannel.update })
MenuHandlers.add(:pause_menu, :nordeluna_map_emotes, {
  "name" => _INTL("Emotes online"), "order" => 46,
  "condition" => proc { !$game_temp.in_battle },
  "effect" => proc { |menu|
    menu.pbHideMenu
    begin
      NordelunaOnline.map_emotes_menu
    ensure
      menu.pbShowMenu
    end
    next false
  }
})
