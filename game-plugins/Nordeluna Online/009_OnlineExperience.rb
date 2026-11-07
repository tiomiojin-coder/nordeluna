class PokemonGlobalMetadata
  attr_accessor :nordeluna_online_receipts
end

module NordelunaOnline
  class ConnectionLost < Error; end
  class VersionMismatch < Error; end

  def self.safe_label(value)
    value.to_s.gsub(/[<>\x00-\x1f]/, "")[0, 80]
  end

  def self.pokemon_summary(pokemon)
    { "name" => pokemon.name, "species" => pokemon.speciesName,
      "level" => pokemon.level, "shiny" => pokemon.shiny?,
      "item" => pokemon.item ? pokemon.item.name : _INTL("Nenhum"),
      "owner" => pokemon.owner.name, "personal_id" => pokemon.personalID }
  end

  def self.summary_text(summary)
    _INTL("{1} ({2}) - Nv. {3}\nShiny: {4}\nItem: {5}\nTreinador original: {6}",
      safe_label(summary["name"]), safe_label(summary["species"]), summary["level"],
      summary["shiny"] ? _INTL("Sim") : _INTL("Nao"), safe_label(summary["item"]), safe_label(summary["owner"]))
  end

  def self.receipts
    $PokemonGlobal.nordeluna_online_receipts || []
  end

  class TradePreview
    def self.confirm(outgoing, incoming, partner)
      unless defined?(Viewport) && defined?(BitmapSprite) && defined?(PokemonIconSprite)
        return pbConfirmMessage(_INTL("VOCE ENVIA:\n{1}\n\nVOCE RECEBE DE {2}:\n{3}\n\nConfirmar? O jogo sera salvo.",
          NordelunaOnline.summary_text(NordelunaOnline.pokemon_summary(outgoing)),
          NordelunaOnline.safe_label(partner),
          NordelunaOnline.summary_text(NordelunaOnline.pokemon_summary(incoming))))
      end
      sprites = {}
      viewport = Viewport.new(0, 0, Graphics.width, Graphics.height)
      viewport.z = 99999
      canvas = BitmapSprite.new(Graphics.width, Graphics.height, viewport)
      sprites["background"] = canvas
      bitmap = canvas.bitmap
      bitmap.fill_rect(0, 0, Graphics.width, Graphics.height, Color.new(12, 22, 39))
      bitmap.font.size = 20
      bitmap.font.color = Color.new(240, 245, 255)
      bitmap.draw_text(0, 8, Graphics.width, 28, _INTL("Confirmar troca com {1}", NordelunaOnline.safe_label(partner)), 1)
      width = (Graphics.width - 36) / 2
      [outgoing, incoming].each_with_index do |pokemon, side|
        x = 12 + side * (width + 12)
        bitmap.fill_rect(x, 46, width, Graphics.height - 150, Color.new(24, 43, 67))
        bitmap.font.size = 17
        bitmap.draw_text(x, 52, width, 24, side == 0 ? _INTL("VOCE ENVIA") : _INTL("VOCE RECEBE"), 1)
        icon = PokemonIconSprite.new(pokemon, viewport)
        icon.x = x + width / 2 - 32
        icon.y = 77
        sprites["pokemon#{side}"] = icon
        icon.update
        info = NordelunaOnline.pokemon_summary(pokemon)
        lines = ["#{NordelunaOnline.safe_label(info['name'])} - Nv. #{info['level']}",
          NordelunaOnline.safe_label(info["species"]),
          _INTL("Shiny: {1}", info["shiny"] ? _INTL("Sim") : _INTL("Nao")),
          _INTL("Item: {1}", NordelunaOnline.safe_label(info["item"])),
          _INTL("OT: {1}", NordelunaOnline.safe_label(info["owner"]))]
        bitmap.font.size = 15
        lines.each_with_index { |line, i| bitmap.draw_text(x + 8, 144 + i * 22, width - 16, 22, line, 1) }
      end
      pbConfirmMessage(_INTL("Confirmar esta troca? O jogo sera salvo automaticamente.")) do
        pbUpdateSpriteHash(sprites)
      end
    ensure
      pbDisposeSpriteHash(sprites) if sprites && defined?(pbDisposeSpriteHash)
      viewport.dispose if viewport && !viewport.disposed?
    end
  end

  module Experience
    def request(url, data)
      started = now
      reply = super
      @connection_latency_ms = ((now - started) * 1000).round
      reply
    rescue Error => error
      if error.message.match?(/versoes do jogo sao diferentes|Protocolo incompativel/i)
        raise VersionMismatch, _INTL("As versoes nao sao compativeis. Atualize os dois jogos para a mesma versao.")
      end
      if error.message.match?(/Servidor sem resposta|Falha de rede|Resposta HTTP invalida|Resposta JSON invalida|Batalha encerrada|Sala nao encontrada/i)
        raise ConnectionLost, _INTL("A conexao foi interrompida. A partida terminou sem atribuir vitoria por queda.")
      end
      raise
    end

    def test_connection(show = true)
      reply = nil
      with_waiting(_INTL("Testando conexao")) { reply = request(server, "action" => "health") }
      unless reply["protocol"] == PROTOCOL && reply["revision"].is_a?(Integer) && reply["revision"] >= 2
        raise VersionMismatch, _INTL("Servidor incompativel. Atualize o relay para revisao 2 ou superior.")
      end
      result = { "server" => server, "latency_ms" => @connection_latency_ms,
        "protocol" => reply["protocol"], "revision" => reply["revision"], "build" => BUILD }
      if show
        pbMessage(_INTL("Servidor acessivel!\nLatencia: {1} ms\nProtocolo: {2} / revisao {3}\nCliente: {4}\nA versao do outro jogador e conferida ao entrar na sala.",
          result["latency_ms"], result["protocol"], result["revision"], VERSION))
      end
      result
    end

    def deliver_trade(committed)
      ticket = pending_trade
      raise Error, "Sem troca pendente." unless ticket
      previous = @receipt_candidate
      @receipt_candidate = {
        "id" => "#{ticket['code']}:#{ticket['side']}", "timestamp" => Time.now.to_i,
        "partner" => ticket["partner"], "status" => committed ? "completed" : "cancelled",
        "sent" => pokemon_summary(PokemonCodec.decode(ticket["outgoing"])),
        "received" => pokemon_summary(PokemonCodec.decode(ticket[committed ? "incoming" : "outgoing"])),
        "save_confirmed" => true
      }
      super
    ensure
      @receipt_candidate = previous
    end

    def save_trade!
      return super unless @receipt_candidate && !pending_trade
      old = $PokemonGlobal.nordeluna_online_receipts
      updated = (old || []).reject { |row| row["id"] == @receipt_candidate["id"] }
      $PokemonGlobal.nordeluna_online_receipts = (updated + [@receipt_candidate]).last(50)
      begin
        super
      rescue StandardError
        $PokemonGlobal.nordeluna_online_receipts = old
        raise
      end
    end

    def start_trade(session, room, slot)
      other = room.fetch("players")[1 - session.side]
      incoming_packet = other.fetch("payload").fetch(0)
      outgoing_packet = room["players"][session.side]["payload"][0]
      incoming = PokemonCodec.decode(incoming_packet)
      outgoing = $player.party.fetch(slot)
      raise Error, "A oferta local mudou. Crie outra sala." unless PokemonCodec.encode(outgoing) == outgoing_packet
      unless TradePreview.confirm(outgoing, incoming, other["profile"]["name"])
        session.call("cancel")
        return
      end
      reserve_trade(session, slot, outgoing_packet, incoming_packet, other["profile"]["name"])
      resolve_trade(session, session.call("confirm"))
    end

    def show_trade_history
      loop do
        history = receipts.reverse
        if history.empty?
          pbMessage(_INTL("Nenhuma troca registrada neste save."))
          return
        end
        labels = history.map do |row|
          _INTL("{1}: {2} > {3}", Time.at(row["timestamp"]).strftime("%d/%m %H:%M"),
            safe_label(row["sent"]["name"]), safe_label(row["received"]["name"]))
        end
        labels << _INTL("Voltar")
        choice = pbMessage(_INTL("Comprovantes de troca"), labels, labels.length)
        return if choice < 0 || choice >= history.length
        row = history[choice]
        pbMessage(_INTL("{1}\nParceiro: {2}\nEnviado:\n{3}\nRecebido:\n{4}\nGravacao: confirmada no save.",
          row["status"] == "completed" ? _INTL("Troca concluida") : _INTL("Cancelada - Pokemon devolvido"),
          safe_label(row["partner"]), summary_text(row["sent"]), summary_text(row["received"])))
      end
    end

    def start_battle(session, room)
      trainers = room.fetch("players").map do |entry|
        data = entry.fetch("profile")
        raise VersionMismatch, "Tipo de treinador desconhecido. Atualize os jogos." unless GameData::TrainerType.exists?(data["type"])
        trainer = NPCTrainer.new(data["name"], data["type"])
        trainer.id = data["id"]
        trainer.lose_text = trainer.win_text = "Boa batalha!"
        trainer
      end
      parties = prepare_online_parties(room["players"], room.fetch("rules"))
      choose_online_lead(session, room, parties)
      trainers.each_with_index { |trainer, i| trainer.party = parties[i] }
      pbMessage(_INTL("Compatibilidade confirmada. Seu Pokemon aparece embaixo; o adversario, em cima."))
      scene = BattleCreationHelperMethods.create_battle_scene
      battle = LinkBattle.new(scene, parties, trainers, session, room.fetch("seed"))
      result = 0
      failure = nil
      pbBattleAnimation(pbGetTrainerBattleBGM(trainers[1 - session.side])) do
        pbSceneStandby do
          begin
            result = battle.pbStartBattle
          rescue StandardError => error
            failure = error
          end
        end
      end
      Input.update
      raise failure if failure
      text = if result == 5 then "Empate!"
             elsif result == 0 then "Batalha online interrompida. Nenhuma vitoria atribuida."
             elsif (result == 1 && session.side == 0) || (result == 2 && session.side == 1)
               "Voce venceu o PvP!"
             else "Voce perdeu o PvP. Bora tentar de novo!"
             end
      pbMessage(_INTL(text))
      result
    end

    def open
      return unless $player && $PokemonGlobal
      loop do
        if pending_trade
          recover_trade
          return if pending_trade
        end
        labels = [_INTL("Testar conexao"), _INTL("PvP: criar sala"), _INTL("PvP: entrar em sala"),
          _INTL("Troca: criar sala"), _INTL("Troca: entrar em sala"), _INTL("Comprovantes de troca"),
          _INTL("Servidor"), _INTL("Meu nick"), _INTL("Emotes no mapa"), _INTL("Sair")]
        choice = pbMessage(_INTL("Nordeluna Online - {1}\nNick: {2}", VERSION, nickname), labels, labels.length)
        case choice
        when 0 then test_connection
        when 1 then connect("battle", false)
        when 2 then connect("battle", true)
        when 3 then connect("trade", false)
        when 4 then connect("trade", true)
        when 5 then show_trade_history
        when 6 then configure_server
        when 7 then configure_nickname
        when 8 then return :sent if map_emotes_menu == :sent
        else return
        end
      end
    rescue ConnectionLost => error
      pbMessage(error.message)
      pbMessage(_INTL("Existe uma troca pendente. Ela continua reservada no save; use Recuperar troca.")) if pending_trade
    rescue Error => error
      pbMessage(_INTL("Online: {1}", error.message))
    rescue StandardError => error
      begin
        File.open("nordeluna-online-errors.log", "ab") do |file|
          file.write("\n[#{Time.now}] #{error.class}: #{error.message}\n#{error.backtrace.join("\n")}\n")
        end
      rescue StandardError
      end
      pbMessage(_INTL("A sessao online foi interrompida. Nenhuma vitoria por queda. Exporte o relatorio de erro para investigar."))
    end
  end
  singleton_class.prepend(Experience)

  def self.offer_pending_recovery
    return unless $player && $PokemonGlobal && pending_trade
    return if @recovery_prompt_active || !defined?(Scene_Map) || !$scene.is_a?(Scene_Map)
    return if !$game_temp || $game_temp.in_battle || $game_temp.in_menu || $game_temp.message_window_showing
    return if $game_map && $game_map.interpreter.running?
    key = [pending_trade["url"], pending_trade["code"], pending_trade["side"]]
    return if @recovery_notified_ticket == key
    @recovery_notified_ticket = key
    @recovery_prompt_active = true
    begin
      if pbConfirmMessage(_INTL("Existe uma troca pendente no seu save. Verificar e recuperar agora?"))
        recover_trade
      end
    rescue Error => error
      pbMessage(_INTL("Recuperacao pendente: {1}\nSeu Pokemon continua reservado no save.", error.message))
    ensure
      @recovery_prompt_active = false
    end
  end
end

MenuHandlers.add(:pause_menu, :nordeluna_pending_trade, {
  "name" => _INTL("Troca pendente - recuperar"), "order" => 44,
  "condition" => proc { $PokemonGlobal && NordelunaOnline.pending_trade },
  "effect" => proc { |menu|
    menu.pbHideMenu
    begin
      NordelunaOnline.open
    ensure
      menu.pbShowMenu
    end
    next false
  }
})
EventHandlers.add(:on_frame_update, :nordeluna_online_pending_recovery,
  proc { NordelunaOnline.offer_pending_recovery })
