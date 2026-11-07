class PokemonGlobalMetadata
  attr_accessor :nordeluna_online_nickname
end

module NordelunaOnline
  module ProfileAndRules
    def nickname
      value = $PokemonGlobal && $PokemonGlobal.nordeluna_online_nickname
      value.is_a?(String) && !value.empty? ? value : _INTL("Sem nick")
    end

    def valid_nickname?(name)
      name.is_a?(String) && name.length.between?(1, 24) && name == name.strip &&
        !name.match?(/[\\<>\x00-\x1f]/)
    end

    def configure_nickname
      old = $PokemonGlobal.nordeluna_online_nickname
      value = pbMessageFreeText(_INTL("Seu nick online (nao altera Leo Farias na historia):"), old || "", false, 24).strip
      return false if value.empty?
      raise Error, "Use de 1 a 24 caracteres, sem barras ou sinais < e >." unless valid_nickname?(value)
      return true if value == old
      return false unless pbConfirmMessage(_INTL("Usar {1} no online? O progresso atual sera salvo. Voce pode mudar o nick depois.", value))
      $PokemonGlobal.nordeluna_online_nickname = value
      begin
        raise Error, "Nao foi possivel gravar o nick. Tente salvar novamente." unless Game.save
      rescue StandardError
        $PokemonGlobal.nordeluna_online_nickname = old
        raise
      end
      pbMessage(_INTL("Nick online salvo: {1}.", value))
      true
    end

    def profile
      value = $PokemonGlobal.nordeluna_online_nickname
      raise Error, "Configure seu nick em Online > Meu nick." unless valid_nickname?(value)
      { "name" => value, "id" => $player.id, "type" => $player.trainer_type.to_s }
    end

    def ruleset(value)
      return super unless value.is_a?(Hash)
      valid = value.keys.sort == %w[count format legendaries level] &&
        value["level"].is_a?(Integer) && [0, 25, 50, 100].include?(value["level"]) &&
        value["count"].is_a?(Integer) && value["count"].between?(1, 6) &&
        [true, false].include?(value["legendaries"]) && %w[single double].include?(value["format"])
      valid &&= value["format"] != "double" || value["count"] >= 2
      raise Error, "Regras da sala invalidas. Atualize os dois jogos." unless valid
      level = value["level"] == 0 ? nil : value["level"]
      description = _INTL("{1}; {2}; {3} Pokemon; lendarios {4}",
        value["format"] == "double" ? _INTL("Dupla") : _INTL("Simples"),
        level ? _INTL("Nv. {1}", level) : _INTL("nivel atual"), value["count"],
        value["legendaries"] ? _INTL("permitidos") : _INTL("bloqueados"))
      { :name => description, :description => description, :level => level,
        :count => value["count"], :legendaries => value["legendaries"], :format => value["format"] }
    end

    def choose_room_rules
      rule = { "level" => 50, "count" => 3, "legendaries" => false, "format" => "single" }
      loop do
        choice = pbMessage(_INTL("Regras: {1}", ruleset(rule)[:name]),
          [_INTL("Nivel"), _INTL("Quantidade"), _INTL("Lendarios"), _INTL("Simples / dupla"), _INTL("Continuar"), _INTL("Cancelar")], 6)
        case choice
        when 0
          n = pbMessage(_INTL("Nivel dos Pokemon (somente copias do PvP):"), [_INTL("Atual"), "25", "50", "100", _INTL("Voltar")], 5)
          rule["level"] = [0, 25, 50, 100][n] if n.between?(0, 3)
        when 1
          minimum = rule["format"] == "double" ? 2 : 1
          counts = (minimum..6).to_a
          n = pbMessage(_INTL("Quantos Pokemon cada jogador deve levar?"), counts.map(&:to_s) + [_INTL("Voltar")], counts.length + 1)
          rule["count"] = counts[n] if n >= 0 && n < counts.length
        when 2 then rule["legendaries"] = !rule["legendaries"]
        when 3
          rule["format"] = rule["format"] == "single" ? "double" : "single"
          rule["count"] = [2, rule["count"]].max if rule["format"] == "double"
        when 4 then return rule
        else return nil
        end
      end
    end

    def restricted_legendary?(pokemon)
      # Species/forms use the Essentials PBS flags; no fragile species-ID list.
      data = GameData::Species.get_species_form(pokemon.species, pokemon.form_simple)
      %w[Legendary Mythical UltraBeast].any? { |flag| data.has_flag?(flag) }
    end

    def select_online_team(rule_id)
      rule = ruleset(rule_id)
      team = $player.party.reject { |p| p.egg? || (!rule.fetch(:legendaries, true) && restricted_legendary?(p)) }
      required = rule[:count] || [6, team.length].min
      raise Error, _INTL("Voce precisa de {1} Pokemon elegiveis. Confira ovos e a regra de lendarios.", required) if required < 1 || team.length < required
      chosen = []
      while chosen.length < required
        remaining = team.reject { |p| chosen.include?(p) }
        labels = remaining.map { |p| _INTL("{1} - Nv. {2}", p.name, p.level) } + [_INTL("Cancelar")]
        n = pbMessage(_INTL("Escolha a equipe: {1}/{2}", chosen.length + 1, required), labels, labels.length)
        return nil if n < 0 || n >= remaining.length
        chosen << remaining[n]
      end
      chosen.map { |p| PokemonCodec.encode(p) }
    end

    def prepare_online_parties(players, rule_id)
      teams = super
      rule = ruleset(rule_id)
      teams.each do |team|
        raise Error, "A equipe nao corresponde a quantidade da sala." if rule[:count] && team.length != rule[:count]
        raise Error, "A sala nao permite lendarios, miticos ou Ultra Beasts." if !rule.fetch(:legendaries, true) && team.any? { |p| restricted_legendary?(p) }
      end
      teams
    end

    def choose_online_lead(session, room, parties)
      rule = ruleset(room.fetch("rules"))
      return super unless rule[:format] == "double"
      pbMessage(_INTL("{1}\nAdversario: {2}\n{3}", rule[:name], room["players"][1 - session.side]["profile"]["name"],
        parties[1 - session.side].map { |p| _INTL("{1} - Nv. {2}", p.speciesName, p.level) }.join("\n")))
      team = parties[session.side]
      selected = []
      2.times do
        indices = team.each_index.reject { |i| selected.include?(i) }
        n = pbMessage(_INTL("Escolha o {1}o Pokemon inicial:", selected.length + 1),
          indices.map { |i| team[i].name } + [_INTL("Cancelar")], indices.length + 1)
        raise Cancelled, "Partida cancelada antes do inicio." if n < 0 || n >= indices.length
        selected << indices[n]
      end
      pair = session.exchange("preview:0", { "leads" => selected, "rules" => room["rules"] })
      parties.each_with_index do |party, side|
        row = pair[side]
        leads = row.is_a?(Hash) && row["leads"]
        valid = row.is_a?(Hash) && row["rules"] == room["rules"] && leads.is_a?(Array) && leads.length == 2 &&
          leads.uniq.length == 2 && leads.all? { |i| i.is_a?(Integer) && i.between?(0, party.length - 1) }
        raise Error, "Selecao inicial invalida." unless valid
        parties[side] = leads.map { |i| party[i] } + party.each_with_index.reject { |_, i| leads.include?(i) }.map(&:first)
      end
      parties
    end

    def connect(mode, join)
      session = nil
      return unless valid_nickname?($PokemonGlobal.nordeluna_online_nickname) || configure_nickname
      MapChannel.disconnect if defined?(MapChannel)
      rule_id = "free"
      data = { "action" => join ? "join" : "create", "mode" => mode, "profile" => profile, "build" => build }
      url = server
      if join
        code = pbMessageFreeText(_INTL("Digite o codigo de 8 caracteres da sala."), "", false, 8).strip.upcase
        return if code.empty?
        raise Error, "Codigo de sala invalido." unless code.match?(/\A[A-Z2-9]{8}\z/)
        info = request(url, "action" => "inspect", "code" => code)
        raise VersionMismatch, "Atualize os dois jogos para a mesma versao." unless info["build"] == build
        raise Error, "Essa sala e de outro modo." unless info["mode"] == mode
        data["code"] = code
        rule_id = info["rules"]
      elsif mode == "battle"
        health = test_connection(false)
        raise VersionMismatch, "Atualize o servidor para revisao 3 antes de criar salas personalizadas." if health["revision"] < 3
        rule_id = choose_room_rules
        return unless rule_id
        data["rules"] = rule_id
      end
      if mode == "battle"
        pbMessage(_INTL("Regras da sala: {1}", ruleset(rule_id)[:description]))
        return unless pbConfirmMessage(_INTL("Aceitar estas regras e escolher a equipe?"))
        data["payload"] = select_online_team(rule_id)
        return unless data["payload"]
      else
        slot = pick_trade_pokemon
        return if slot.nil?
        data["payload"] = [PokemonCodec.encode($player.party[slot])]
      end
      reply = request(url, data)
      session = Session.new(url, reply)
      session.rules = reply["rules"]
      raise Error, "As regras da sala mudaram. Crie outra sala." if mode == "battle" && reply["rules"] != rule_id
      pbMessage(_INTL("Sala: {1}. Envie esse codigo ao outro jogador. VOLTAR cancela a espera.", session.code)) unless join
      room = session.wait_for { |r| r["players"].length == 2 }
      mode == "battle" ? start_battle(session, room) : start_trade(session, room, slot)
    ensure
      session.call("cancel") rescue nil if session && !pending_trade
    end
  end
  singleton_class.prepend(ProfileAndRules)

  class Session
    attr_accessor :rules
  end

  module DoubleLinkBattle
    def initialize(scene, parties, trainers, session, seed)
      super
      rules = session.respond_to?(:rules) && session.rules
      setBattleMode("double") if rules && NordelunaOnline.ruleset(rules)[:format] == "double"
    end

    def online_choose_double_action(idx)
      return { "kind" => "forced" } unless pbCanShowCommands?(idx)
      loop do
        cmd = @scene.pbCommandMenu(idx, idx == @online_side)
        if cmd > 0 && @battlers[idx].effects[PBEffects::SkyDrop] >= 0
          pbDisplay(_INTL("Seu Pokemon precisa esperar o Sky Drop terminar."))
          next
        end
        case cmd
        when 0
          if pbFightMenu(idx)
            move = @choices[idx][2]
            if @choices[idx][1] >= 0 && @choices[idx][3] < 0 && move.pbTarget(@battlers[idx]).num_targets == 1
              next unless pbChooseTarget(@battlers[idx], move)
            end
            return { "kind" => "move", "index" => @choices[idx][1], "target" => @choices[idx][3], "mega" => pbRegisteredMegaEvolution?(idx) }
          end
        when 1 then pbDisplay(_INTL("A Bolsa nao pode ser usada no PvP online."))
        when 2
          n = pbPartyScreen(idx, false, true, true)
          return { "kind" => "switch", "index" => n } if n >= 0
        when 3
          return { "kind" => "forfeit" } if pbDisplayConfirm(_INTL("Desistir desta batalha?"))
        end
        pbCancelChoice(idx)
      end
    end

    def online_apply_action(idx, action)
      return super if singleBattle?
      if action.is_a?(Hash) && action["kind"] == "move" && pbCanShowCommands?(idx)
        n = action["index"]
        raise Error, "Golpe invalido." unless n.is_a?(Integer) && n.between?(-1, 3)
        valid = n == -1 ? (!pbCanShowFightMenu?(idx) && pbAutoChooseMove(idx, false)) : pbRegisterMove(idx, n, false)
        raise Error, "Golpe indisponivel." unless valid
        mega = action.fetch("mega", false)
        raise Error, "Mega invalida." unless [true, false].include?(mega)
        if mega
          raise Error, "Mega indisponivel." unless pbCanMegaEvolve?(idx)
          pbRegisterMegaEvolution(idx)
        end
        target = action["target"]
        raise Error, "Alvo invalido." unless target.is_a?(Integer) && target.between?(-1, 3)
        if target >= 0
          move = @choices[idx][2]
          raise Error, "Alvo indisponivel." unless @battlers[target] && !@battlers[target].fainted? && pbMoveCanTarget?(idx, target, move.pbTarget(@battlers[idx]))
        elsif @choices[idx][2].pbTarget(@battlers[idx]).num_targets == 1 && n != -1
          # The engine's auto-choice (e.g. Encore) can use its default target.
          raise Error, "Escolha um alvo para o golpe." if pbCanShowFightMenu?(idx)
        end
        pbRegisterTarget(idx, target)
      else
        super
      end
    end

    def pbCommandPhase
      return super if singleBattle?
      @command_phase = true
      @scene.pbBeginCommandPhase
      @battlers.each_with_index { |b, i| pbClearChoice(i) if b && pbCanShowCommands?(i) }
      online_sync("state:#{@turnCount}", online_state)
      local = []
      [@online_side, @online_side + 2].each do |i|
        local << online_choose_double_action(i)
        break if local.last["kind"] == "forfeit"
      end
      local << { "kind" => "forced" } while local.length < 2
      pair = @online_session.exchange("turn:#{@turnCount}", { "actions" => local }) { |window| @scene.pbFrameUpdate(window) }
      raise Error, "Comandos da dupla invalidos." unless pair.is_a?(Array) && pair.length == 2 && pair.all? { |r| r.is_a?(Hash) && r["actions"].is_a?(Array) && r["actions"].length == 2 && r["actions"].all? { |a| a.is_a?(Hash) } }
      @battlers.each_with_index { |b, i| pbClearChoice(i) if b && pbCanShowCommands?(i) }
      2.times { |side| @megaEvolution[side][0] = -1 if @megaEvolution[side][0] >= 0 }
      surrendered = pair.map { |r| r["actions"].any? { |a| a["kind"] == "forfeit" } }
      if surrendered.any?
        @decision = surrendered.all? ? 5 : (surrendered[0] ? 2 : 1)
      else
        4.times { |idx| online_apply_action(idx, pair[idx % 2]["actions"][idx / 2]) }
      end
    ensure
      @command_phase = false
    end

    def pbSwitchInBetween(idx, lax = false, can_cancel = false)
      return super if singleBattle?
      key = "switch:#{@online_switch_count}"
      @online_switch_count += 1
      owner = idx % 2
      choice = owner == @online_side ? pbPartyScreen(idx, lax, can_cancel, false) : nil
      pair = @online_session.exchange(key, choice) { |window| @scene.pbFrameUpdate(window) }
      n = pair[owner]
      valid = n.is_a?(Integer) && n.between?(-1, 5) && pair[1 - owner].nil?
      valid &&= n == -1 ? can_cancel : (lax ? pbCanSwitchIn?(idx, n) : pbCanSwitch?(idx, n))
      raise Error, "Substituicao da dupla invalida." unless valid
      n
    end
  end
  LinkBattle.prepend(DoubleLinkBattle)
end
