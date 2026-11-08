module NordelunaOnline
  module AreaChannel
    attr_accessor :foreground_request
    def connect(room = nil)
      acquired = false
      raise Error, "Ja existe uma conexao de area em andamento." if @area_connecting || Areas.busy?
      return true if Areas.active? && active? && (!room || NordelunaOnline.room_name(room) == room_name)
      @area_connecting = true
      acquired = true
      health = NordelunaOnline.test_connection(false)
      raise VersionMismatch, "Areas online precisam do servidor revisao 5." if health["revision"].to_i < 5
      Areas.validate_configuration(health)
      return false unless super
      pbMessage(_INTL("Conexao com o servidor realizada com sucesso!"))
      unless pbConfirmMessage(_INTL("Deseja entrar na Praca Central Online?"))
        disconnect
        pbMessage(_INTL("Voce foi desconectado do servidor online."))
        return false
      end
      Areas.enter(@area_join_reply)
      true
    rescue StandardError
      disconnect if acquired && (managed? || active?)
      raise
    ensure
      @area_connecting = false if acquired
    end

    def join_payload
      value = super
      value["account"] = Identity.ensure_registered
      value["area_map"] = $game_map.map_id if Areas.active? && Areas.online_map?($game_map.map_id)
      value
    end

    def accept_join(reply)
      Areas.validate_configuration(reply)
      @area_join_reply = reply
      @last_position_signature = @last_position_sent = nil
      @next_keepalive = 0
      super
    end

    def position
      @position_sequence = (@position_sequence || 0) + 1
      super.merge("direction" => $game_player.direction, "character" => $game_player.character_name,
        "frame" => $game_player.pattern, "moving" => $game_player.moving?, "seq" => @position_sequence)
    end

    def room_context?
      Areas.active? && $game_map && Areas.online_map?($game_map.map_id) && !Areas.busy? && !Areas.restoring? &&
        !foreground_request && $scene.is_a?(Scene_Map) && !$game_temp.in_battle
    end

    def keepalive
      acquired = false
      return unless managed? && active? && @desired && !@suspended
      return if @worker || @updating || @keeping_alive || foreground_request
      return if Areas.active? && !Areas.busy? && !Areas.restoring?
      return if NordelunaOnline.now < (@next_keepalive || 0)
      @keeping_alive = true
      acquired = true
      @next_keepalive = NordelunaOnline.now + 3
      start_room_request({"action"=>"map_ping", "token"=>@token,
        "after"=>@chat_cursor || 0,"chat_epoch"=>@chat_epoch}, :ping)
    rescue StandardError => error
      connection_failed(error)
    ensure
      @keeping_alive = false if acquired
    end

    def start_room_request(data, operation)
      if operation == :update
        signature = data["state"].reject { |key, _| key == "seq" }
        urgent = data["chat"] || data["emote"]
        heartbeat=members<=1 ? 5.0 : POSITION_HEARTBEAT
        return false if !urgent && signature == @last_position_signature && NordelunaOnline.now - (@last_position_sent || -10) < heartbeat
        @last_position_signature = signature
        @last_position_sent = NordelunaOnline.now
        data = data.merge("known_peers" => Ghosts.known_metadata)
      end
      super(data, operation)
    end

    def collect
      ticket = @worker
      snapshot = nil
      if managed? && ticket && !ticket.alive? && @operation == :update
        result = ticket.value
        raw = result.is_a?(Hash) && (result[:body] || result["body"])
        snapshot = JSON.parse(raw) if raw.is_a?(String) && raw.bytesize <= MAX_RESPONSE
        if snapshot.is_a?(Hash) && snapshot["ok"] == true &&
           (snapshot["request_sequence"] != @sent_position["seq"] || snapshot["map"] != $game_map.map_id)
          @worker = nil
          return # Response from a previous map/request must not resurrect ghosts.
        end
      end
      super
      if snapshot && snapshot["ok"] == true && Areas.active? && snapshot["map"] == $game_map.map_id
        Ghosts.synchronize(snapshot.fetch("peers"))
      end
    end

    def connection_failed(error)
      super
      if Areas.active?
        @desired = false
        Areas.connection_lost
      end
    end

    def disconnect
      acquired = false
      return if @area_disconnecting
      @area_disconnecting = true
      acquired = true
      Areas.guarded do
        begin
          super
        ensure
          Ghosts.clear
          Areas.restore if Areas.anchor && !Areas.restoring?
        end
      end
    ensure
      @area_disconnecting = false if acquired
    end

    def abandon
      Ghosts.clear
      super
    end
  end
  MapChannel.singleton_class.prepend(AreaChannel)

  module AreaSceneCleanup
    def dispose
      Ghosts.clear
      super
    end
  end
  Scene_Map.prepend(AreaSceneCleanup)

  module AreaForegroundGate
    def request(url, data)
      previous = MapChannel.foreground_request
      MapChannel.foreground_request = true
      super
    ensure
      MapChannel.foreground_request = previous
    end
  end
  singleton_class.prepend(AreaForegroundGate)

  # Menus may update Graphics without Scene_Map's on_frame_update event. Keep
  # the existing async transport alive; no sprite/warp work runs in its worker.
  module AreaMenuFrames
    def update(*args)
      result = super
      if MapChannel.managed? && $scene.is_a?(Scene_Map)
        MapChannel.update
        MapChannel.keepalive
        Ghosts.update if defined?(Ghosts) && Areas.active? && !Areas.busy? && !Areas.restoring?
      end
      result
    end
  end
  Graphics.singleton_class.prepend(AreaMenuFrames)
end
