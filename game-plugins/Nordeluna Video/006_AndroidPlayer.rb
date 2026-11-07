# Files carry only bounded data. Decoding and display run in Android's player,
# outside Ruby and without loading Windows DLLs or launching an executable.
module NordelunaVideo
  module AndroidPlayer
    class << self
      def directory
        File.join(Dir.pwd, ".nordeluna-movie-bridge")
      end

      def read_marker(name)
        path = File.join(directory, name)
        return nil unless File.file?(path)
        raise "Resposta do player de video invalida." if File.size(path) > 4096
        File.binread(path).force_encoding("UTF-8")
      end

      def ready_session
        deadline = NordelunaVideo.clock + 3
        loop do
          session = read_marker("session")
          status = read_marker("status").to_s.split("\n", 2)
          return session if session && session.match?(/\A[0-9a-f-]{36}\z/) && status[0] == "1"
          if NordelunaVideo.clock >= deadline
            raise "Atualize o APK para reproduzir os videos no Android. Se ja atualizou, feche e abra o aplicativo."
          end
          Graphics.update
          Input.update
        end
      end

      def play(path, volume, skippable, options = {})
        raise "Caminho de video invalido." if path.match?(/[\r\n\x00]/)
        session = ready_session
        id = Random.bytes(16).unpack1("H*")
        request = File.join(directory, "#{id}.request")
        temporary = File.join(directory, "#{id}.writing")
        response = File.join(directory, "#{id}.response")
        cancel = File.join(directory, "#{id}.cancel")
        packet = [session, path, volume, skippable ? 1 : 0,
                  options.fetch(:tempo_pular, 1.2), options.fetch(:entrada, 0.0),
                  options.fetch(:saida, 0.0), options[:duracao].to_f].join("\n")
        raise "Pedido de video grande demais." if packet.bytesize > 8192
        File.binwrite(temporary, packet)
        File.rename(temporary, request)
        heartbeat = nil
        changed_at = NordelunaVideo.clock
        finished = false
        begin
          loop do
            if File.file?(response)
              raise "Resposta do video grande demais." if File.size(response) > 4096
              status, message = File.binread(response).force_encoding("UTF-8").split("\n", 2)
              finished = true
              raise message.to_s if status == "ERROR"
              raise "Resposta do player de video invalida." unless status == "OK"
              return true
            end
            raise "O player de video foi reiniciado. Tente novamente." if read_marker("session") != session
            status = read_marker("status").to_s
            now = NordelunaVideo.clock
            if status != heartbeat || status.start_with?("0\n")
              heartbeat = status
              changed_at = now
            end
            raise "O player de video parou de responder. Tente novamente." if now - changed_at > 15
            Graphics.update
            Input.update
          end
        ensure
          File.binwrite(cancel, "1") unless finished
          [temporary, response].each { |file| File.delete(file) if File.file?(file) }
        end
      rescue Errno::ENOENT, Errno::EACCES
        raise "O player de video esta indisponivel. Reinicie o aplicativo e confira a atualizacao do APK."
      end
    end
  end
end
