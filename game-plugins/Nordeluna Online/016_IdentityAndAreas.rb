class PokemonGlobalMetadata
  attr_accessor :nordeluna_online_identity, :nordeluna_online_identities, :nordeluna_online_return
end

module NordelunaOnline
  # Only configured areas are enabled. Other map IDs remain pending.
  PLAZA_MAP_ID = 39
  COLISEUM_MAP_ID = nil
  MARKET_MAP_ID = nil
  ONLINE_MAP_IDS = [PLAZA_MAP_ID, COLISEUM_MAP_ID, MARKET_MAP_ID].compact.freeze
  PLAZA_ENTRY = { :x => 34, :y => 59, :direction => 8 }.freeze
  NICK_FONT_SIZE = 18
  NICK_COLOR = [255, 255, 255].freeze
  NICK_OUTLINE = [24, 32, 48].freeze
  NICK_OFFSET = 8
  REMOTE_DISTANCE = 18
  SHOW_NICKNAMES = true
  POSITION_INTERVAL = 0.25
  POSITION_HEARTBEAT = 3.0

  module Identity
    class << self
      def credentials
        endpoint = NordelunaOnline.server
        previous = $PokemonGlobal.nordeluna_online_identity
        previous_pool = $PokemonGlobal.nordeluna_online_identities
        pool = previous_pool.is_a?(Hash) ? previous_pool.dup : {}
        value = pool[endpoint]
        if pool.empty? && previous.is_a?(Hash) && previous["id"].to_s.match?(/\A[0-9a-f]{32}\z/) && previous["secret"].to_s.match?(/\A[0-9a-f]{64}\z/)
          value = previous # Preserve an earlier single-server identity during migration.
          pool[endpoint] = value
        end
        valid = value.is_a?(Hash) && value["id"].to_s.match?(/\A[0-9a-f]{32}\z/) && value["secret"].to_s.match?(/\A[0-9a-f]{64}\z/)
        return value if valid && previous == value && previous_pool.is_a?(Hash)
        value = { "id" => Random.bytes(16).unpack1("H*"), "secret" => Random.bytes(32).unpack1("H*") } unless valid
        pool[endpoint] = value
        $PokemonGlobal.nordeluna_online_identities = pool
        $PokemonGlobal.nordeluna_online_identity = value
        begin
          Areas.checked_save!
        rescue StandardError
          $PokemonGlobal.nordeluna_online_identity = previous
          $PokemonGlobal.nordeluna_online_identities = previous_pool
          raise
        end
        value
      end

      def register(name)
        raise Error, "Nick: use 3 a 16 letras A-Z, numeros ou underscore." unless NordelunaOnline.valid_nickname?(name)
        data = credentials
        existing = nil
        begin
          existing = NordelunaOnline.request(NordelunaOnline.server, "action"=>"account_info", "account"=>data)
        rescue Error => error
          raise unless error.message.include?("Identidade online invalida")
        end
        query = { "action"=>"account_check", "nickname"=>name }
        query["account"] = data if existing && existing["id"] == data["id"]
        available = NordelunaOnline.request(NordelunaOnline.server, query)
        raise Error, "Este nickname ja esta sendo utilizado. Escolha outro." unless available["available"] == true
        reply = NordelunaOnline.request(NordelunaOnline.server,
          "action" => "account_register", "account" => data, "nickname" => name)
        raise Error, "Identidade retornada pelo servidor invalida." unless reply["id"] == data["id"] && NordelunaOnline.valid_nickname?(reply["nickname"])
        $PokemonGlobal.nordeluna_online_nickname = reply["nickname"]
        Areas.checked_save!
        @registered = [NordelunaOnline.server, data["id"], reply["nickname"]]
        reply
      end

      def ensure_registered
        data = credentials
        name = $PokemonGlobal.nordeluna_online_nickname
        return data if @registered == [NordelunaOnline.server, data["id"], name]
        unless NordelunaOnline.valid_nickname?(name)
          raise Cancelled, "Configure um nick valido antes de conectar." unless NordelunaOnline.configure_nickname
          return credentials
        end
        begin
          # Reconcile a rename that succeeded remotely but whose local save failed.
          reply = NordelunaOnline.request(NordelunaOnline.server, "action" => "account_info", "account" => data)
          raise Error, "Identidade retornada pelo servidor invalida." unless reply["id"] == data["id"] && NordelunaOnline.valid_nickname?(reply["nickname"])
          if name != reply["nickname"]
            $PokemonGlobal.nordeluna_online_nickname = reply["nickname"]
            Areas.checked_save!
          end
          @registered = [NordelunaOnline.server, data["id"], reply["nickname"]]
        rescue Error => error
          raise unless error.message.include?("Identidade online invalida")
          register(name)
        end
        data
      end

      def reset_cache; @registered = nil; end
    end
  end

  module RegisteredIdentity
    def valid_nickname?(name)
      name.is_a?(String) && name.match?(/\A[A-Za-z0-9_]{3,16}\z/)
    end

    def configure_nickname
      MapChannel.disconnect if MapChannel.managed? || MapChannel.active?
      old = $PokemonGlobal.nordeluna_online_nickname.to_s
      value = pbMessageFreeText(_INTL("Nick exclusivo: 3 a 16 letras, numeros ou underscore."), old, false, 16)
      return false if value.empty?
      raise Error, "Nick: use 3 a 16 letras A-Z, numeros ou underscore, sem espacos." unless valid_nickname?(value)
      return false unless pbConfirmMessage(_INTL("Registrar {1} no servidor e salvar? O nome da historia permanece igual.", value))
      health = test_connection(false)
      raise VersionMismatch, "Nick exclusivo precisa do servidor revisao 5. Atualize o servidor." unless health["revision"].to_i >= 5
      Identity.register(value)
      pbMessage(_INTL("Nick exclusivo salvo: {1}.", value))
      true
    end

    def configure_server
      MapChannel.disconnect if MapChannel.managed? || MapChannel.active?
      value = pbMessageFreeText(_INTL("Endereco do servidor online:"), server, false, 160)
      return if value.strip.empty?
      value = validate_url(value)
      reply = request(value, "action" => "health")
      raise VersionMismatch, "Atualize o servidor para a revisao 5." unless reply["protocol"] == PROTOCOL && reply["revision"].to_i >= 5
      old = $PokemonGlobal.nordeluna_online_server
      $PokemonGlobal.nordeluna_online_server = value
      begin
        Areas.checked_save!
      rescue StandardError
        $PokemonGlobal.nordeluna_online_server = old
        raise
      end
      Identity.reset_cache
      @identity_health_server = nil
      pbMessage(_INTL("Endereco verificado e salvo. Entre em Sala e chat para conectar as areas online."))
    end

    def request(url, data)
      if %w[create join map_join].include?(data["action"])
        health = test_connection(false) unless @identity_health_server == url
        if health
          raise VersionMismatch, "Atualize o servidor para a revisao 5." if health["revision"].to_i < 5
          @identity_health_server = url
        end
        data = data.merge("account" => Identity.ensure_registered)
      end
      super(url, data)
    end
  end
  singleton_class.prepend(RegisteredIdentity)
end
