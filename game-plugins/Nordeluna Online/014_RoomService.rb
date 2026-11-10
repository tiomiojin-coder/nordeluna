module NordelunaOnline
  class << self
    def record_online_error(error, action = nil)
      @last_online_error = { "message" => safe_label(error.respond_to?(:message) ? error.message : error),
        "time" => Time.now.to_i, "action" => action.to_s[0, 32] }
    end

    def observe_server(reply, latency = nil)
      CosmeticBadges.receive(reply['badge']) if defined?(CosmeticBadges) && reply.key?('badge')
      Friends.observe(reply["social"]) if defined?(Friends) && reply["social"]
      @server_diagnostic = {} if reply.key?("protocol") && reply.key?("revision")
      @server_diagnostic ||= {}
      %w[version revision protocol].each { |key| @server_diagnostic[key] = reply[key] if reply.key?(key) }
      @server_diagnostic["latency_ms"] = latency if latency
      if latency.is_a?(Numeric) && latency.finite? && latency.between?(0,60000)
        @latency_samples=[] if @latency_server!=server
        @latency_server=server
        @latency_samples=((@latency_samples || [])+[latency]).last(20)
        @server_diagnostic['latency_average_ms']=(@latency_samples.sum.to_f/@latency_samples.length).round
        @server_diagnostic['latency_samples']=@latency_samples.length
        @server_diagnostic['latency_range_ms']=(@latency_samples.max-@latency_samples.min).round
      end
      processing=reply['server_ms']
      @server_diagnostic.delete('server_ms')
      if processing.is_a?(Numeric) && processing.finite? && processing.between?(0,60000)
        @server_diagnostic['server_ms']=processing.round(2)
      end
    end

    def diagnostic_snapshot
      { "client" => VERSION, "build" => BUILD, "server" => server,
        "remote" => (@server_diagnostic || {}).dup,
        "room" => MapChannel.room_name, "state" => MapChannel.connection_label,
        "last_error" => @last_online_error && @last_online_error.dup }
    end

    def room_name(value)
      value = value.to_s.strip.upcase
      raise Error, "Use PRACA ou um codigo de 8 letras/numeros de 2 a 9." unless value == "PRACA" || value.match?(/\A[A-Z2-9]{8}\z/)
      value
    end
  end

  module DiagnosticMonitor
    def request(url, data)
      started = now
      result = super
      observe_server(result, ((now - started) * 1000).round)
      result
    rescue StandardError => error
      record_online_error(error, data.is_a?(Hash) ? data["action"] : nil)
      raise
    end
  end
  SafeTransport.prepend(DiagnosticMonitor)

  module RoomChannel
    def managed?; !!@room_managed; end
    def room_name; @room || "PRACA"; end
    def messages; @messages ||= []; end
    def members; @members || 0; end
    def desired?; !!@desired; end
    def notice; @notice; end
    def revision; @revision || 0; end

    def connection_label
      case @connection_state
      when :connected then "Conectado"
      when :connecting then "Conectando"
      when :reconnecting then "Reconectando (tentativa #{@retry_attempt || 1})"
      when :suspended then "Pausado para batalha/troca"
      else "Desconectado"
      end
    end

    def connect(room = nil)
      begun = false
      selected = NordelunaOnline.room_name(room || room_name)
      return true if managed? && active? && selected == @room
      disconnect if active? || managed?
      return false unless NordelunaOnline.valid_nickname?($PokemonGlobal.nordeluna_online_nickname) || NordelunaOnline.configure_nickname
      @room_managed = true
      begun = true
      @room = selected
      @url = NordelunaOnline.server
      @room_build = NordelunaOnline.build
      @messages = []
      @chat_cursor = 0
      @chat_epoch = nil
      @outbox = nil
      @desired = true
      @retry_until = nil
      @retry_at = @retry_attempt = 0
      @suspended = false
      @connection_state = :connecting
      @bubbles ||= {}
      @sequences = {}
      @last_emote = @last_chat = -10
      health = NordelunaOnline.test_connection(false)
      raise VersionMismatch, "Salas e chat precisam do servidor revisao 4. Atualize o servidor." if health["revision"] < 4
      reply = NordelunaOnline.request(@url, join_payload)
      accept_join(reply)
      true
    rescue VersionMismatch
      @desired = false
      @connection_state = :disconnected
      NordelunaOnline.record_online_error($!, "map_join")
      raise
    rescue StandardError => error
      connection_failed(error) if begun
      raise
    end

    def join_payload
      { "action" => "map_join", "room" => room_name, "resume" => @resume_token,
        "profile" => NordelunaOnline.profile, "build" => @room_build }
    end

    def accept_join(reply)
      raise Error, "O servidor retornou outra sala." unless reply["room"] == @room
      raise Error, "Sessao de sala invalida." unless reply["token"].is_a?(String) && reply["token"].length.between?(16, 256) && reply["id"].is_a?(String)
      if @resume_token && !reply["resumed"] && @outbox && @outbox[:attempted]
        @outbox = nil
        @notice = "Mensagem anterior sem confirmacao. Confira o historico antes de reenviar."
      else
        @notice = @connection_state == :reconnecting ? "Conexao restaurada na sala #{@room}." : "Voce entrou na sala #{@room}."
      end
      @token = @resume_token = reply.fetch("token")
      @id = reply.fetch("id")
      @connection_state = :connected
      @retry_attempt = 0
      @retry_until = nil
      @error = nil
      @next_poll = 0
      @operation = nil
      @sequences ||= {}
      NordelunaOnline.observe_server(reply)
      @revision = revision + 1
    end

    def connection_failed(error)
      @worker.cancel if @worker
      @worker = nil
      @token = nil
      if error.is_a?(MapSessionExpired)
        @resume_token = nil
        @outbox = nil if @outbox && @outbox[:attempted]
      end
      @error = error.message
      NordelunaOnline.record_online_error(error, "map_room")
      if @desired && !@suspended
        @retry_until ||= NordelunaOnline.now + 60
        @retry_attempt = (@retry_attempt || 0) + 1
        @retry_at = NordelunaOnline.now + [1, 2, 4, 8, 12][[@retry_attempt - 1, 4].min]
        @connection_state = :reconnecting
        @notice = "Conexao perdida. Tentando voltar a sala #{@room}."
      else
        @connection_state = @suspended ? :suspended : :disconnected
      end
      @revision = revision + 1
    end

    def disconnect
      return super unless managed?
      @desired = false
      @suspended = false
      drain
      old = @token || @resume_token
      @token = @resume_token = nil
      @outbox = nil
      @queued = @sent_emote = nil
      @connection_state = :disconnected
      dispose_bubbles
      NordelunaOnline.request(@url, "action" => "map_leave", "token" => old) if old
    rescue StandardError => error
      NordelunaOnline.record_online_error(error, "map_leave")
    ensure
      @room_managed = false
      @messages = []
      ChatPanel.dispose if defined?(ChatPanel)
    end

    def suspend
      return disconnect unless managed?
      ChatPanel.hide if defined?(ChatPanel)
      @suspended = true
      drain
      @connection_state = :suspended
      dispose_bubbles
    end

    def resume
      return unless managed? && @desired
      @suspended = false
      @token = nil
      @retry_at = NordelunaOnline.now
      @retry_until = NordelunaOnline.now + 60
      @connection_state = :reconnecting
    end

    def abandon
      @desired = false
      @worker.cancel if @worker
      @worker = nil
      @token = @resume_token = nil
      @outbox = nil
      @connection_state = :disconnected
      @room_managed = false
      @messages = []
      dispose_bubbles
      ChatPanel.dispose if defined?(ChatPanel)
    end

    def queue_message(text)
      raise Error, "Entre em uma sala primeiro." unless managed? && @desired
      text = text.to_s.strip
      raise Error, "Use de 1 a 120 caracteres, sem tags ou quebras de linha." unless text.length.between?(1, 120) && !text.match?(/[<>\x00-\x1f\x7f]/)
      raise Error, "Aguarde a confirmacao da mensagem anterior." if @outbox
      raise Error, "Espere 2 segundos entre mensagens." if NordelunaOnline.now - (@last_chat || -10) < 2
      @outbox = { :id => Random.bytes(16).unpack1("H*"), :text => text, :attempted => false }
      @notice = "Mensagem aguardando confirmacao."
      @next_poll = 0
      @revision = revision + 1
    end

    def drain
      return super unless managed?
      acquired = false
      return if @draining
      @draining = acquired = true
      ticket, deadline = @worker, @worker_deadline
      if ticket
        while @worker.equal?(ticket) && ticket.alive?
          raise ConnectionLost, "Servidor sem resposta." if NordelunaOnline.now >= deadline
          Graphics.update
          Input.update
        end
        collect if @worker.equal?(ticket)
      end
    rescue StandardError => error
      connection_failed(error)
    ensure
      @draining = false if acquired
    end

    def collect
      return super unless managed?
      return unless @worker && !@worker.alive?
      result = @worker.value
      @worker = nil
      raise ConnectionLost, "Sala sem resposta." unless result.is_a?(Hash)
      raw = result[:body] || result["body"]
      raise ConnectionLost, "Resposta de sala invalida." unless raw.is_a?(String) && raw.bytesize <= MAX_RESPONSE
      reply = JSON.parse(raw)
      unless reply.is_a?(Hash) && reply["ok"] == true
        message = reply.is_a?(Hash) ? reply["error"].to_s : "Resposta de sala invalida."
        raise MapSessionExpired, "A sessao online expirou. Entre novamente na sala." if NordelunaOnline.map_session_expired?(message)
        if message.match?(/Espere 2|Mensagem:|ID de mensagem/)
          @outbox = nil
          @notice = "Mensagem nao enviada: #{message}"
          NordelunaOnline.record_online_error(Error.new(message), "chat")
          @revision = revision + 1
          return
        end
        raise ConnectionLost, message
      end
      NordelunaOnline.observe_server(reply, ((NordelunaOnline.now - @request_started) * 1000).round)
      return accept_join(reply) if @operation == :join
      raise Error, "Resposta de outra sala." unless reply["room"] == @room
      raise Error, "Historico de chat invalido." unless reply["messages"].is_a?(Array) && reply["messages"].length <= 80 && reply["chat_epoch"].is_a?(String)
      if @chat_epoch != reply["chat_epoch"]
        @messages = []
        @chat_cursor = 0
        @chat_epoch = reply["chat_epoch"]
      end
      reply["messages"].each do |row|
        valid = row.is_a?(Hash) && row["id"].is_a?(Integer) && row["id"] > 0 && row["timestamp"].is_a?(Integer) &&
          row["timestamp"].between?(0, 4_102_444_800) && row["nick"].is_a?(String) && row["text"].is_a?(String) && row["text"].length <= 120
        raise Error, "Mensagem recebida invalida." unless valid
        next if row["id"] <= @chat_cursor
        messages << { "id" => row["id"], "nick" => NordelunaOnline.safe_label(row["nick"]),
          "text" => row["text"].gsub(/[<>\x00-\x1f\x7f]/, ""), "timestamp" => row["timestamp"] }
        @chat_cursor = row["id"]
      end
      @messages = messages.last(80)
      @members = reply["members"].is_a?(Integer) ? reply["members"] : 0
      if @outbox && reply["chat_ack"] == @outbox[:id]
        @outbox = nil
        @last_chat = NordelunaOnline.now
        @notice = "Mensagem enviada."
      end
      if $game_map && @sent_position && @sent_position["map"] == $game_map.map_id
        peers = reply["peers"]
        raise Error, "Lista de jogadores invalida." unless peers.is_a?(Array) && peers.length <= 40
        peers.each { |peer| receive(peer) }
        if @sent_emote
          show_bubble(@id, NordelunaOnline.nickname, @sent_emote, @sent_position["x"], @sent_position["y"])
          @last_emote = NordelunaOnline.now
        end
      end
      @sent_emote = nil
      @revision = revision + 1
    end

    def start_room_request(data, operation)
      @operation = operation
      @request_started = NordelunaOnline.now
      @worker_deadline = @request_started + REQUEST_TIMEOUT
      @worker = Transport.start(@url, data)
    end

    def room_context?
      return true if safe_map?
      defined?(ChatPanel) && ChatPanel.modal? && $scene.is_a?(Scene_Map) && !$game_temp.in_battle
    end

    def update
      return super unless managed?
      return if @updating || @draining
      @updating = true
      begin
        if @worker
          raise ConnectionLost, "Servidor sem resposta." if @worker.alive? && NordelunaOnline.now >= @worker_deadline
          collect unless @worker.alive?
        end
        safe = room_context?
        update_bubbles(safe_map?) if $game_map
        return unless safe && @desired && !@suspended && !@worker
        if !active?
          if @retry_until && NordelunaOnline.now >= @retry_until
            @desired = false
            @connection_state = :disconnected
            @notice = "Nao foi possivel reconectar em 60 segundos. Use Reconectar."
            @revision = revision + 1
            return
          end
          return if NordelunaOnline.now < (@retry_at || 0)
          start_room_request(join_payload, :join)
        elsif NordelunaOnline.now >= (@next_poll || 0)
          @sent_position = position
          @sent_emote = @queued
          @queued = nil
          data = { "action" => "map_update", "token" => @token, "state" => @sent_position,
            "emote" => @sent_emote, "chat_enabled" => true, "after" => @chat_cursor || 0, "chat_epoch" => @chat_epoch }
          if @outbox
            data["chat"] = { "client_id" => @outbox[:id], "text" => @outbox[:text] }
          end
          start_room_request(data, :update)
          @outbox[:attempted] = true if @outbox
          @next_poll = NordelunaOnline.now + (defined?(POSITION_INTERVAL) ? POSITION_INTERVAL : 1)
        end
      rescue StandardError => error
        @queued ||= @sent_emote
        @sent_emote = nil
        connection_failed(error)
      ensure
        @updating = false
      end
    end
  end
  MapChannel.singleton_class.prepend(RoomChannel)
end
