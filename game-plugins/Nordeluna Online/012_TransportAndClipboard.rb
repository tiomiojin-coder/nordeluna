module NordelunaOnline
  module Transport
    class << self
      def android?
        defined?(System) && System.respond_to?(:is_android?) && System.is_android?
      end

      def start(url, data)
        busy = false
        begin
          busy = @active && @active.alive?
        rescue Error
          @active.cancel
        end
        raise ConnectionLost, "Um pedido anterior ainda esta terminando. Aguarde alguns segundos." if busy
        body = JSON.dump(data.merge("protocol" => PROTOCOL))
        raise Error, "Equipe grande demais." if body.bytesize > 262144
        endpoint = NordelunaOnline.validate_url(url) + "/api"
        @active = android? ? AndroidTicket.new(endpoint, body) : DesktopTicket.new(endpoint, body)
      end
    end

    class AndroidTicket
      def initialize(endpoint, body)
        @directory = File.join(Dir.pwd, ".nordeluna-online-bridge")
        @session = File.binread(File.join(@directory, "session"))
        raise ConnectionLost, "Atualize o APK para usar o transporte online seguro." unless ready?
        @id = Random.bytes(16).unpack1("H*")
        temporary = path("writing")
        File.binwrite(temporary, @session + "\n" + endpoint + "\n" + body)
        File.rename(temporary, path("request"))
      rescue Errno::ENOENT, Errno::EACCES
        raise ConnectionLost, "Transporte Android indisponivel. Atualize o APK e abra o jogo novamente."
      end

      def path(extension); File.join(@directory, "#{@id}.#{extension}"); end

      def ready?
        status = File.join(@directory, "status")
        File.file?(status) && File.binread(status) == "1" && Time.now.to_f - File.mtime(status).to_f < 4
      end

      def alive?
        return false if @cancelled || @result
        if File.file?(path("response"))
          raise ConnectionLost, "Resposta Android grande demais." if File.size(path("response")) > MAX_RESPONSE + 1024
          raw = File.binread(path("response"))
          File.delete(path("response"))
          status, body = raw.split("\n", 2)
          raise ConnectionLost, body.to_s if status == "ERROR"
          raise ConnectionLost, "Resposta do transporte Android invalida." unless status.match?(/\A[1-5][0-9]{2}\z/)
          @result = { :status => status.to_i, :body => body.to_s.force_encoding("UTF-8") }
          return false
        end
        raise ConnectionLost, "Conexao interrompida. O aplicativo foi pausado ou reiniciado." unless ready? && File.binread(File.join(@directory, "session")) == @session
        true
      rescue Errno::ENOENT
        raise ConnectionLost, "O transporte Android foi reiniciado. Abra outra sala."
      end

      def value
        raise ConnectionLost, "Pedido cancelado." if @cancelled
        raise Error, "Pedido ainda em andamento." if alive?
        @result
      end

      def cancel
        return if @cancelled || !@id
        @cancelled = true
        if File.file?(path("request"))
          File.binwrite(path("cancel"), "1")
        end
        File.delete(path("response")) if File.file?(path("response"))
      rescue SystemCallError
      end
    end

    class DesktopTicket
      def initialize(endpoint, body)
        raise Error, "O runtime precisa de HTTPLite." unless defined?(HTTPLite) && HTTPLite.respond_to?(:post_body)
        @worker = Thread.new do
          begin
            HTTPLite.post_body(endpoint, body, "application/json", { "Accept" => "application/json" })
          rescue StandardError
            nil
          end
        end
      end
      def alive?; @worker.alive?; end
      def join; @worker.join; self; end
      def value; @cancelled ? nil : @worker.value; end
      # Never kill a thread executing native HTTP code. Keep it registered until
      # completion so a new request cannot overlap a cancelled desktop request.
      def cancel; @cancelled = true; end
    end
  end

  module SafeTransport
    def request(url, data)
      started = now
      ticket = Transport.start(url, data)
      deadline = started + REQUEST_TIMEOUT
      while ticket.alive?
        frame
        raise ConnectionLost, "Servidor sem resposta. Verifique a internet e tente novamente." if now >= deadline
      end
      result = ticket.value
      raise ConnectionLost, "Falha de rede. Verifique o servidor e tente novamente." unless result.is_a?(Hash)
      raw = result[:body] || result["body"]
      raise ConnectionLost, "Resposta HTTP invalida." unless raw.is_a?(String) && raw.bytesize <= MAX_RESPONSE
      reply = JSON.parse(raw)
      unless reply.is_a?(Hash) && reply["ok"] == true
        message = reply.is_a?(Hash) ? reply["error"].to_s : "Resposta invalida."
        raise VersionMismatch, "As versoes nao sao compativeis. Atualize os dois jogos." if message.match?(/versoes do jogo sao diferentes|Protocolo incompativel/i)
        raise ConnectionLost, "A conexao foi interrompida. Nenhuma vitoria por queda." if message.match?(/Batalha encerrada|Sala nao encontrada/)
        raise Error, message
      end
      @connection_latency_ms = ((now - started) * 1000).round
      reply
    ensure
      ticket.cancel if ticket
    end
  end
  # Keep MapNetworkGate outermost: it drains map requests before foreground I/O.
  Experience.prepend(SafeTransport)

  def self.show_room_code(code)
    raise Error, "Codigo de sala invalido." unless code.is_a?(String) && code.match?(/\A[A-Z2-9]{8}\z/)
    loop do
      choice = pbMessage(_INTL("Sala: {1}\nEnvie o codigo ao outro jogador.", code),
        [_INTL("Copiar codigo"), _INTL("Aguardar jogador"), _INTL("Cancelar sala")], 3)
      case choice
      when 0
        begin
          raise Error, "Este runtime nao oferece area de transferencia." unless Input.respond_to?(:clipboard=)
          Input.clipboard = code
          pbMessage(_INTL("Codigo copiado! Cole no WhatsApp ou envie ao outro jogador."))
        rescue StandardError
          pbMessage(_INTL("Nao foi possivel copiar. Codigo da sala: {1}", code))
        end
      when 1 then return true
      else raise Cancelled, "Sala cancelada."
      end
    end
  end
end
