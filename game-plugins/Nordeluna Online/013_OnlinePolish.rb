module NordelunaOnline
  def self.run_pause_action(menu)
    ended = false
    menu.pbHideMenu
    begin
      if yield == :sent
        menu.pbEndScene
        $game_temp.in_menu = false
        ended = true
        return true
      end
      false
    ensure
      menu.pbShowMenu unless ended
    end
  end

  module TeamDiagnostics
    def select_online_team(rule_id)
      rule = ruleset(rule_id)
      eligible = []
      blocked = []
      $player.party.each do |pokemon|
        reason = if pokemon.egg? then "ovo"
                 elsif !GameData::Species.exists?(pokemon.species) then "especie ausente nesta versao"
                 elsif !rule.fetch(:legendaries, true) && restricted_legendary?(pokemon) then "lendario/mitico/Ultra Beast bloqueado"
                 end
        if reason
          blocked << "#{pokemon.name}: #{reason}"
        else
          eligible << pokemon
        end
      end
      required = rule[:count] || [6, eligible.length].min
      if required < 1 || eligible.length < required
        raise Error, _INTL("Equipe: {1} de {2} elegiveis.\n{3}", eligible.length, required, blocked.join("\n"))
      end
      chosen = []
      if eligible.length == required && pbConfirmMessage(_INTL("Usar os {1} Pokemon da equipe?\n{2}", required, eligible.map(&:name).join(", ")))
        chosen = eligible
      end
      while chosen.length < required
        remaining = eligible.reject { |p| chosen.include?(p) }
        labels = remaining.map { |p| _INTL("{1} - Nv. {2}", p.name, p.level) } + [_INTL("Cancelar")]
        n = pbMessage(_INTL("Escolha a equipe: {1}/{2}", chosen.length + 1, required), labels, labels.length)
        return nil if n < 0 || n >= remaining.length
        chosen << remaining[n]
      end
      chosen.map do |pokemon|
        begin
          packet = PokemonCodec.encode(pokemon)
          PokemonCodec.decode(packet) # Validate each offered species before connecting.
          packet
        rescue StandardError => error
          raise Error, _INTL("Nao foi possivel preparar {1} ({2}): {3}", pokemon.name, pokemon.species, error.message)
        end
      end
    end
  end
  singleton_class.prepend(TeamDiagnostics)

  module MegaChoice
    def pbCanMegaEvolve?(idx)
      battler = @battlers[idx]
      return false if !battler || battler.fainted? || !battler.hasMega? || battler.mega?
      return false if battler.effects[PBEffects::SkyDrop] >= 0
      return false if defined?(PBEffects::Commander) && battler.effects[PBEffects::Commander]
      state = @megaEvolution[battler.idxOwnSide][pbGetOwnerIndexFromBattlerIndex(idx)]
      state == -1 || state == idx
    end

    def online_mega_prompt(idx)
      return unless pbCanMegaEvolve?(idx)
      choice = pbShowCommands(_INTL("{1}: usar Mega Evolucao neste turno?", @battlers[idx].name),
        [_INTL("Mega Evoluir e escolher golpe"), _INTL("Escolher golpe sem Mega")], 1)
      if choice == 0
        pbRegisterMegaEvolution(idx)
      else
        pbUnregisterMegaEvolution(idx)
      end
    end

    def pbFightMenu(idx)
      # Interactive scenes get an explicit choice; the engine's ACTION shortcut remains.
      interactive = @scene.is_a?(Battle::Scene) || @scene.is_a?(LocalScene)
      online_mega_prompt(idx) if interactive && !pbRegisteredMegaEvolution?(idx)
      super
    end
  end
  LinkBattle.prepend(MegaChoice)
end

MenuHandlers.add(:pause_menu, :nordeluna_online, {
  "name" => _INTL("Online"), "order" => 45,
  "condition" => proc { !$game_temp.in_battle },
  "effect" => proc { |menu| next NordelunaOnline.run_pause_action(menu) { NordelunaOnline.open } }
})
