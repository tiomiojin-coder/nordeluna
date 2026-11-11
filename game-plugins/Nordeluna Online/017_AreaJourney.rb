module NordelunaOnline
  module Areas
    class << self
      def configured?
        PLAZA_MAP_ID.is_a?(Integer) && PLAZA_MAP_ID > 0 && ONLINE_MAP_IDS.include?(PLAZA_MAP_ID) &&
          ONLINE_MAP_IDS.length.between?(1, 3) && ONLINE_MAP_IDS.uniq.length == ONLINE_MAP_IDS.length &&
          ONLINE_MAP_IDS.all? { |id| id.is_a?(Integer) && id > 0 }
      end
      def online_map?(id); ONLINE_MAP_IDS.include?(id); end
      def anchor; $PokemonGlobal && $PokemonGlobal.nordeluna_online_return; end
      def active?; !!@inside && !!anchor; end
      def busy?; !!@busy; end
      def saving?; !!@saving; end
      def online_location?
        !!($game_map && online_map?($game_map.map_id))
      end
      def save_notice
        pbMessage(_INTL("Você só pode salvar fora da Praça Central, do Mercado Global e do Coliseu Lunar. Saia da área online e tente novamente."))
        false
      end

      def select_save_slot(slot)
        path = REInterface.save_path(slot)
        raise IOError, "Caminho do slot invalido." unless path.is_a?(String) && !path.empty?
        @default_save_path ||= SaveData::FILE_PATH
        set_save_path(path)
      end

      def set_save_path(path)
        return if SaveData::FILE_PATH == path
        SaveData.send(:remove_const, :FILE_PATH)
        SaveData.const_set(:FILE_PATH, path)
      end

      def reset_save_path
        set_save_path(@default_save_path) if @default_save_path
      end

      def transaction_save
        previous = @saving
        raise Error, "Nao ha um retorno seguro da campanha. Saia da area online antes de continuar." if online_location? && !anchor
        @saving = true
        yield
      ensure
        @saving = previous
      end

      def campaign_save_hash(saved)
        return saved unless online_location?
        raise IOError, "Salvamento manual bloqueado nas areas online." unless saving? && anchor
        validate_location(anchor, true)
        # Reuse only trusted local campaign positioning. The deserialized objects
        # are independent of the running map/player; no live teleport occurs.
        previous = Marshal.load(File.binread(SaveData::FILE_PATH))
        raise IOError, "O save anterior da campanha esta invalido." unless previous.is_a?(Hash)
        factory, player = previous[:map_factory], previous[:game_player]
        point = anchor
        raise IOError, "O save anterior nao contem o retorno seguro da campanha." unless
          factory && factory.respond_to?(:map) && factory.map && factory.map.map_id == point["map"] &&
          player && [player.x, player.y, player.direction] == [point["x"], point["y"], point["direction"]]
        saved[:map_factory], saved[:game_player] = factory, player
        saved[:map_metadata] = previous[:map_metadata] if previous.key?(:map_metadata)
        saved[:global_metadata].safesave = true if saved[:global_metadata].respond_to?(:safesave=)
        saved
      rescue TypeError, ArgumentError, EOFError, Error
        raise IOError, "Nao foi possivel recuperar a posicao segura da campanha. O save anterior foi preservado."
      end

      def guarded
        previous = @busy
        @busy = true
        yield
      ensure
        @busy = previous
      end

      def checked_save!
        previous = @saving
        @saving = true
        raise Error, "Nao foi possivel salvar. O transporte foi cancelado." unless Game.save
        # Read the trusted local save, never a network-supplied Marshal payload.
        saved = Marshal.load(File.binread(SaveData::FILE_PATH))
        global = saved[:global_metadata]
        raise Error, "O ponto de retorno nao foi confirmado no save." unless global && global.nordeluna_online_return == anchor
        true
      ensure
        @saving = previous
      end

      def validate_location(point, campaign = false)
        raise Error, "Ponto de retorno invalido." unless point.is_a?(Hash) &&
          %w[map x y direction].all? { |key| point[key].is_a?(Integer) } && [2, 4, 6, 8].include?(point["direction"])
        raise Error, "Uma area online nao pode ser o retorno da campanha." if campaign && online_map?(point["map"])
        map = load_data(format("Data/Map%03d.rxdata", point["map"]))
        raise Error, "O ponto configurado esta fora do mapa." unless map.respond_to?(:width) && map.respond_to?(:height) &&
          point["x"].between?(0, map.width - 1) && point["y"].between?(0, map.height - 1)
        point
      rescue Errno::ENOENT
        raise Error, "Mapa configurado nao encontrado. Confira os IDs das areas e do retorno."
      end

      def validate_configuration(reply)
        raise Error, "Configure o ID da Praca Central antes de entrar. Os outros dois mapas podem ficar pendentes." unless configured?
        expected = { "plaza" => PLAZA_MAP_ID, "coliseum" => COLISEUM_MAP_ID, "market" => MARKET_MAP_ID }
        raise VersionMismatch, "Os IDs das areas do cliente e do servidor nao correspondem." unless reply["areas"] == expected
        validate_location({ "map" => PLAZA_MAP_ID, "x" => PLAZA_ENTRY[:x], "y" => PLAZA_ENTRY[:y], "direction" => PLAZA_ENTRY[:direction] })
      end

      def enter(reply)
        created_anchor = saved_anchor = false
        acquired = false
        raise Error, "Ja existe uma entrada ou retorno em andamento." if busy?
        @busy = true
        acquired = true
        validate_configuration(reply)
        raise Error, "Recupere a troca pendente antes de entrar nas areas online." if NordelunaOnline.pending_trade
        raise Error, "Recupere seu retorno anterior antes de entrar novamente." if anchor
        raise Error, "Conecte pelo mundo principal para registrar seu retorno." if online_map?($game_map.map_id)
        point = { "map" => $game_map.map_id, "x" => $game_player.x, "y" => $game_player.y, "direction" => $game_player.direction }
        point["vehicles"] = %w[surfing diving bicycle].to_h { |key| [key, $PokemonGlobal.respond_to?(key) && !!$PokemonGlobal.send(key)] }
        validate_location(point, true)
        $PokemonGlobal.nordeluna_online_return = point.merge("schema" => 1)
        created_anchor = true
        checked_save!
        saved_anchor = true
        MapChannel.verify_entry!
        pbMessage(_INTL("Seu progresso foi salvo! Voce sera transportado para a Praca Central Online."))
        @inside = true
        target = { "map" => PLAZA_MAP_ID, "x" => PLAZA_ENTRY[:x], "y" => PLAZA_ENTRY[:y], "direction" => PLAZA_ENTRY[:direction] }
        authorize(target["map"])
        transfer(target)
        raise ConnectionLost, "Conexao perdida durante o transporte." unless MapChannel.active? && !@return_pending
        true
      rescue StandardError
        if saved_anchor
          @return_pending = true
          restore
        elsif created_anchor
          $PokemonGlobal.nordeluna_online_return = nil
          @inside = @return_pending = false
        end
        raise
      ensure
        @busy = false if acquired
      end

      def authorize(map)
        previous_busy = @busy
        @busy = true
        raise ConnectionLost, "Conexao de area indisponivel." unless MapChannel.active?
        MapChannel.drain
        raise MapSessionExpired, "A sessao online foi encerrada antes da troca de mapa. Entre novamente na sala." unless MapChannel.active?
        reply = NordelunaOnline.request(NordelunaOnline.server,
          "action" => "map_enter", "token" => MapChannel.instance_variable_get(:@token), "map" => map)
        raise Error, "Transicao nao autorizada pelo servidor." unless reply["map"] == map
      ensure
        @busy = previous_busy
      end

      def transfer(point)
        validate_location(point, !online_map?(point["map"]))
        @transferring = true
        pbFadeOutIn do
          $game_temp.player_transferring = true
          $game_temp.player_new_map_id = point["map"]
          $game_temp.player_new_x, $game_temp.player_new_y = point["x"], point["y"]
          $game_temp.player_new_direction = point["direction"]
          $scene.transfer_player
        end
        Ghosts.clear if defined?(Ghosts)
      ensure
        @transferring = false
      end

      def restoring?; !!@transferring; end
      def connection_lost
        Ghosts.clear if defined?(Ghosts)
        @return_pending = true if active?
      end

      def restore
        point = anchor
        return unless point
        validate_location(point, true)
        @inside = false
        @return_pending = false
        transfer(point)
        restore_vehicles(point)
        $PokemonGlobal.nordeluna_online_return = nil
        checked_save!
      rescue StandardError
        # Keep the original recovery point; no repeated automatic warp attempts.
        $PokemonGlobal.nordeluna_online_return = point if point
        @return_pending = false
        raise
      end

      def recover_loaded
        reset_runtime
        MapChannel.abandon
        Identity.reset_cache
        return unless anchor
        point = validate_location(anchor, true)
        $map_factory.setup(point["map"])
        $game_map = $map_factory.map
        $game_player.moveto(point["x"], point["y"])
        $game_player.send({2=>:turn_down,4=>:turn_left,6=>:turn_right,8=>:turn_up}.fetch(point["direction"]))
        restore_vehicles(point)
        $game_temp.followers.map_transfer_followers if $game_temp.respond_to?(:followers) && $game_temp.followers
        $PokemonGlobal.nordeluna_online_return = nil
        @loaded_notice = true
      end

      def reset_runtime
        @inside = @busy = @return_pending = @loaded_notice = false
      end

      def restore_vehicles(point)
        (point["vehicles"] || {}).each do |key, value|
          next unless %w[surfing diving bicycle].include?(key) && [true,false].include?(value)
          $PokemonGlobal.send("#{key}=", value) if $PokemonGlobal.respond_to?("#{key}=")
        end
        pbUpdateVehicle if defined?(pbUpdateVehicle)
      end

      def update
        return if busy? || restoring? || !$scene.is_a?(Scene_Map)
        connection_lost if active? && (!MapChannel.managed? || !online_map?($game_map.map_id))
        if @return_pending && !$game_temp.in_battle && !$game_temp.in_menu && !$game_temp.message_window_showing && !pbMapInterpreterRunning?
          @busy = true
          begin
            MapChannel.disconnect
            message=defined?(ModerationMessages) && ModerationMessages.take
            pbMessage(message || _INTL("Conexao interrompida. Voce voltou ao ponto salvo da campanha."))
          rescue StandardError => error
            NordelunaOnline.record_online_error(error, "area_return")
            pbMessage(_INTL("Nao foi possivel concluir o retorno: {1}", error.message))
          ensure
            @busy = false
          end
        end
        if @loaded_notice && MapChannel.safe_map?
          @loaded_notice = false
          pbMessage(_INTL("A sessao online anterior foi encerrada. Seu ponto da campanha foi restaurado."))
        end
      end
    end
  end

  module AreaSaveWriter
    def save_to_file(path)
      if Areas.online_location? && !Areas.saving?
        Areas.save_notice
        raise IOError, "Salvamento bloqueado: saia da area online."
      end
      return super unless Areas.saving? || Areas.anchor
      temporary = path + ".online-tmp"
      backup = path + ".online-return.bak"
      begin
        super(temporary)
        saved = Marshal.load(File.binread(temporary))
        raise IOError, "Save sem ponto de retorno valido." unless saved.is_a?(Hash) &&
          saved[:global_metadata]&.nordeluna_online_return == Areas.anchor
        if Areas.online_location?
          saved = Areas.campaign_save_hash(saved)
          File.binwrite(temporary, Marshal.dump(saved))
        end
        if File.file?(path)
          File.binwrite(backup + ".tmp", File.binread(path))
          File.rename(backup + ".tmp", backup)
        end
        File.rename(temporary, path)
      ensure
        File.delete(temporary) if File.file?(temporary)
      end
    end
  end
  SaveData.singleton_class.prepend(AreaSaveWriter)

  module AreaManualSaveGuard
    def save(*args, **kwargs)
      return Areas.save_notice if Areas.online_location? && !Areas.saving?
      super
    end
  end
  Game.singleton_class.prepend(AreaManualSaveGuard)

  module AreaSaveScreenGuard
    def pbSaveScreen(*args)
      return Areas.save_notice if Areas.online_location?
      super
    end
  end
  Object.prepend(AreaSaveScreenGuard)
  PokemonSaveScreen.prepend(AreaSaveScreenGuard) if defined?(PokemonSaveScreen)

  module AreaSlotSaveGuard
    def save_to_slot(*args)
      return Areas.save_notice if Areas.online_location? && !Areas.saving?
      result = super
      Areas.select_save_slot(args[0]) if result
      result
    end

    def load_from_slot(slot, *args)
      previous = SaveData::FILE_PATH
      Areas.select_save_slot(slot)
      result = super
      Areas.set_save_path(previous) unless result
      result
    rescue StandardError
      Areas.set_save_path(previous) if previous
      raise
    end
  end
  REInterface::MultiSave.singleton_class.prepend(AreaSlotSaveGuard) if defined?(REInterface::MultiSave)

  module AreaTradeSaveGuard
    def save_trade!
      return super unless Areas.online_location?
      Areas.transaction_save { super }
    end
  end
  singleton_class.prepend(AreaTradeSaveGuard)

  module AreaLoadRecovery
    def start_new
      MapChannel.abandon
      Areas.reset_runtime
      Areas.reset_save_path
      Identity.reset_cache
      super
    end
    def load_map
      Areas.recover_loaded
      super
    end
  end
  Game.singleton_class.prepend(AreaLoadRecovery)

  module AreaTransferGuard
    def transfer_player(*args)
      unless Areas.restoring?
        target = $game_temp.player_new_map_id
        if Areas.online_map?(target)
          unless Areas.active?
            $game_temp.player_transferring = false
            pbMessage(_INTL("Entre nas areas pela opcao Sala e chat do menu Online."))
            return
          end
          direction = $game_temp.player_new_direction
          direction = $game_player.direction unless [2,4,6,8].include?(direction)
          Areas.validate_location({"map"=>target,"x"=>$game_temp.player_new_x,"y"=>$game_temp.player_new_y,"direction"=>direction})
          Areas.authorize(target)
        elsif Areas.active?
          $game_temp.player_transferring = false
          MapChannel.disconnect
          return
        end
      end
      Ghosts.clear if defined?(Ghosts)
      super
    rescue Error => error
      $game_temp.player_transferring = false
      Areas.connection_lost
      NordelunaOnline.record_online_error(error, "area_transfer")
      pbMessage(_INTL("Transferencia cancelada: {1}", error.message))
    end
  end
  Scene_Map.prepend(AreaTransferGuard)
end

EventHandlers.add(:on_frame_update, :nordeluna_area_recovery, proc { NordelunaOnline::Areas.update })
