#===============================================================================
# Overworld Pokemon Battles - Pokemon Essentials v21.1
#===============================================================================
# OWPKMN(...,SPAWN=CHANCE,TIME=PERIODO,WEATHER=CLIMA,SWITCH=ID)
# Comportamentos: AGGRESSIVE (padrao), CURIOUS, FLEE e STATIC.
#===============================================================================

class OverworldPokemonEmotionSprite < Sprite
  DURATION = 0.75

  def initialize(event, emotion)
    super(nil)
    @event = event
    @start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    if emotion == :ANGER
      self.bitmap = Bitmap.new("Graphics/Battle animations/safari_anger")
    else
      self.bitmap = Bitmap.new(40, 40)
      pbSetSystemFont(self.bitmap)
      self.bitmap.font.size = 26
      self.bitmap.font.bold = true
      self.bitmap.font.color = Color.new(80, 170, 255)
      self.bitmap.draw_text(0, 0, 25, 32, "!", 1)
      # Gotas azuis representam susto/medo sem depender de uma fonte de emoji.
      if emotion == :FEAR
        self.bitmap.fill_rect(27, 8, 5, 11, Color.new(80, 170, 255))
        self.bitmap.fill_rect(28, 5, 3, 4, Color.new(140, 210, 255))
      end
    end
    self.ox = self.bitmap.width / 2
    self.oy = self.bitmap.height
    self.z = 999
    update
  end

  def update
    return if disposed?
    elapsed = [Process.clock_gettime(Process::CLOCK_MONOTONIC) - @start_time, 0.0].max
    if elapsed >= DURATION
      dispose
      return
    end
    self.x = @event.screen_x
    self.y = @event.screen_y - 42 - (Math.sin(elapsed * 12) * 3).round
    self.opacity = (elapsed > 0.55) ? ((DURATION - elapsed) * 1_275).to_i : 255
  end

  def dispose
    return if disposed?
    self.bitmap.dispose if self.bitmap && !self.bitmap.disposed?
    super
  end
end

module OverworldPokemonBattles
  DEFAULT_SIGHT_DISTANCE = 3
  AI_CHECK_INTERVAL      = 6
  DEFAULT_RESPAWN        = 45.0
  DEFAULT_ROAM_RADIUS    = 3
  CONDITION_INTERVAL     = 1.0
  RESPAWN_SAFE_DISTANCE  = 3
  CHASE_STUCK_TIMEOUT    = 4.0
  PATH_NODE_LIMIT        = 80
  SETTINGS_VERSION       = 3
  VALID_BEHAVIORS        = [:AGGRESSIVE, :CURIOUS, :FLEE, :STATIC]
  ESCAPE_CHANCES         = {
    :AGGRESSIVE => 3,
    :STATIC     => 15,
    :CURIOUS    => 50,
    :FLEE       => 100
  }

  class << self
    attr_accessor :busy, :active_battle, :double_capture_battle, :checking_poke_ball
    attr_accessor :choosing_ball_item
    attr_accessor :captured_object_ids
    attr_accessor :current_battle_behaviors, :surprised_object_ids
  end
  self.busy = false
  self.active_battle = false
  self.double_capture_battle = false
  self.checking_poke_ball = false
  self.choosing_ball_item = false
  self.captured_object_ids = []
  self.current_battle_behaviors = []
  self.surprised_object_ids = []

  def self.clear_map_cache
    @settings_cache = {}
    @overworld_events = nil
    @overworld_events_signature = nil
  end

  def self.escape_chance
    chances = self.current_battle_behaviors.map { |behavior| ESCAPE_CHANCES[behavior] || 3 }
    return chances.min || 3
  end

  # [species, min_level, max_level, sight_distance, behavior]
  def self.event_settings(event)
    return nil if !event || !event.name
    cached_name = event.instance_variable_get(:@nordeluna_ow_cached_name)
    if cached_name == event.name &&
       event.instance_variable_get(:@nordeluna_ow_settings_version) == SETTINGS_VERSION &&
       event.instance_variable_defined?(:@nordeluna_ow_cached_settings)
      return event.instance_variable_get(:@nordeluna_ow_cached_settings)
    end
    @settings_cache ||= {}
    cache_key = [event.map_id, event.id, event.name]
    if @settings_cache.key?(cache_key)
      settings = @settings_cache[cache_key]
      cache_event_settings(event, settings)
      return settings
    end
    match = event.name.match(/OWPKMN\s*\(([^\)]+)\)/i)
    if !match
      @settings_cache[cache_key] = nil
      return cache_event_settings(event, nil)
    end
    parts = match[1].split(",").map { |part| part.strip }
    if parts.length < 2
      @settings_cache[cache_key] = nil
      return cache_event_settings(event, nil)
    end
    species = parts[0].upcase.to_sym
    if !GameData::Species.exists?(species)
      @settings_cache[cache_key] = nil
      return cache_event_settings(event, nil)
    end
    level_match = parts[1].match(/\A(\d+)\s*(?:-\s*(\d+))?\z/)
    if !level_match
      @settings_cache[cache_key] = nil
      return cache_event_settings(event, nil)
    end
    min_level = level_match[1].to_i
    max_level = (level_match[2] || level_match[1]).to_i
    min_level, max_level = max_level, min_level if min_level > max_level
    max_allowed = GameData::GrowthRate.max_level
    min_level = [[min_level, 1].max, max_allowed].min
    max_level = [[max_level, 1].max, max_allowed].min
    distance = (parts[2] || DEFAULT_SIGHT_DISTANCE).to_i
    distance = DEFAULT_SIGHT_DISTANCE if distance <= 0
    behavior = :AGGRESSIVE
    options = {
      :spawn_chance => 100,
      :time          => nil,
      :weather       => nil,
      :switch_id     => nil,
      :switch_value  => true,
      :respawn       => DEFAULT_RESPAWN,
      :roam          => DEFAULT_ROAM_RADIUS,
      :habitat       => :AUTO,
      :group         => nil,
      :rest          => 15,
      :form          => nil,
      :shiny         => nil
    }
    parts[3..-1]&.each do |part|
      token = part.upcase
      token_behavior = token.to_sym
      behavior = token_behavior if VALID_BEHAVIORS.include?(token_behavior)
      if token[/\ASPAWN\s*=\s*(\d+)\z/]
        options[:spawn_chance] = [[$1.to_i, 0].max, 100].min
      elsif token[/\ATIME\s*=\s*(DAY|NIGHT|MORNING|AFTERNOON|EVENING)\z/]
        options[:time] = $1.to_sym
      elsif token[/\AWEATHER\s*=\s*(NONE|RAIN|STORM|SNOW|BLIZZARD|SANDSTORM|HEAVYRAIN|SUN|FOG)\z/]
        options[:weather] = $1.to_sym
      elsif token[/\ASWITCH\s*=\s*(!)?(\d+)\z/]
        options[:switch_id] = $2.to_i
        options[:switch_value] = $1.nil?
      elsif token[/\ARESPAWN\s*=\s*(\d+(?:\.\d+)?)\z/]
        options[:respawn] = [[$1.to_f, 0.0].max, 3_600.0].min
      elsif token[/\AROAM\s*=\s*(\d+)\z/]
        options[:roam] = [[$1.to_i, 0].max, 12].min
      elsif token[/\AHABITAT\s*=\s*(AUTO|LAND|WATER|REST)\z/]
        options[:habitat] = $1.to_sym
      elsif token[/\AGROUP\s*=\s*([A-Z0-9_]+)\z/]
        options[:group] = $1
      elsif token[/\AREST\s*=\s*(\d+)\z/]
        options[:rest] = [[$1.to_i, 0].max, 100].min
      elsif token[/\AFORM\s*=\s*(\d+)\z/]
        options[:form] = $1.to_i
      elsif token[/\ASHINY\s*=\s*(0|1|TRUE|FALSE)\z/]
        options[:shiny] = ['1', 'TRUE'].include?($1)
      end
    end
    settings = [species, min_level, max_level, distance, behavior, options]
    @settings_cache[cache_key] = settings
    return cache_event_settings(event, settings)
  end

  def self.cache_event_settings(event, settings)
    event.instance_variable_set(:@nordeluna_ow_settings_version, SETTINGS_VERSION)
    event.instance_variable_set(:@nordeluna_ow_cached_name, event.name)
    event.instance_variable_set(:@nordeluna_ow_cached_settings, settings)
    return settings
  end

  def self.overworld_events
    return [] if !$game_map
    events = $game_map.events
    signature = [$game_map.map_id, events.object_id, events.length]
    if @overworld_events_signature != signature
      @overworld_events_signature = signature
      @overworld_events = events.values.select { |event| !event_settings(event).nil? }
    end
    return @overworld_events || []
  end

  def self.ai_check_due?(event)
    frame = Graphics.frame_count
    key = [$game_player.x, $game_player.y, event.x, event.y, event.direction]
    old_key = event.instance_variable_get(:@nordeluna_ow_ai_key)
    last_frame = event.instance_variable_get(:@nordeluna_ow_ai_frame)
    return false if old_key == key && last_frame && frame >= last_frame &&
                    frame - last_frame < AI_CHECK_INTERVAL
    event.instance_variable_set(:@nordeluna_ow_ai_key, key)
    event.instance_variable_set(:@nordeluna_ow_ai_frame, frame)
    return true
  end

  def self.appearance_conditions_met?(settings)
    options = settings[5]
    case options[:time]
    when :DAY       then return false if !PBDayNight.isDay?
    when :NIGHT     then return false if !PBDayNight.isNight?
    when :MORNING   then return false if !PBDayNight.isMorning?
    when :AFTERNOON then return false if !PBDayNight.isAfternoon?
    when :EVENING   then return false if !PBDayNight.isEvening?
    end
    if options[:weather]
      current_weather = $game_screen&.weather_type || :None
      weather_data = GameData::Weather.try_get(current_weather)
      case options[:weather]
      when :RAIN
        return false if !weather_data || weather_data.category != :Rain
      when :SNOW
        return false if !weather_data || weather_data.category != :Hail
      else
        weather_ids = {
          :NONE      => :None,
          :STORM     => :Storm,
          :BLIZZARD  => :Blizzard,
          :SANDSTORM => :Sandstorm,
          :HEAVYRAIN => :HeavyRain,
          :SUN       => :Sun,
          :FOG       => :Fog
        }
        expected = weather_ids[options[:weather]]
        return false if current_weather != expected
      end
    end
    if options[:switch_id] && options[:switch_id] > 0
      current_value = ($game_switches[options[:switch_id]] == true)
      return false if current_value != options[:switch_value]
    end
    return true
  end

  # Consulta sem efeitos colaterais; o ciclo de vida pertence ao Game_Event.
  def self.spawn_available?(event, settings = nil)
    return event.instance_variable_get(:@ow_pokemon_active) == true
  end

  def self.show_behavior_indicator(event, behavior)
    return if !$scene.is_a?(Scene_Map)
    spriteset = $scene.spriteset(event.map_id)
    return if !spriteset
    emotion = case behavior
              when :AGGRESSIVE then :ANGER
              when :FLEE then :FEAR
              else :NOTICE
              end
    spriteset.addUserSprite(OverworldPokemonEmotionSprite.new(event, emotion))
  end

  def self.map_ready?
    return false if !$scene.is_a?(Scene_Map)
    return false if !$game_player || !$game_map || !$player
    return false if $game_temp.in_menu
    return false if $game_system.map_interpreter.running?
    return false if $game_temp.respond_to?(:in_battle) && $game_temp.in_battle
    return false if $game_temp.message_window_showing || $game_temp.in_mini_update
    return false if self.busy || self.active_battle
    return true
  end

  def self.distance_to_player(event)
    return (event.x - $game_player.x).abs + (event.y - $game_player.y).abs
  end

  # Um segundo agressivo so participa quando tambem alcanca o jogador.
  def self.second_watcher(first_event)
    return overworld_events.find do |event|
      settings = event_settings(event)
      event != first_event && settings && settings[4] == :AGGRESSIVE &&
        spawn_available?(event) && !event.instance_variable_get(:@erased) &&
        event.instance_variable_get(:@page) &&
        event.instance_variable_get(:@ow_pokemon_alerted) &&
        !event.instance_variable_get(:@ow_pokemon_battling) &&
        !event.moving? && !event.jumping? && !event.move_route_forcing &&
        event.ow_contact_reachable?
    end
  end

  def self.captured?(pokemon)
    return self.captured_object_ids.include?(pokemon.object_id)
  end
end

EventHandlers.add(:on_enter_map, :overworld_pokemon_clear_cache, proc { |_old_map_id|
  OverworldPokemonBattles.clear_map_cache
})

# Preserva o handler original de Poké Bolas e altera somente a contagem de alvos
# enquanto ele valida uma batalha dupla deste plugin.
module OverworldPokemonBattles
  if !const_defined?(:ORIGINAL_POKE_BALL_HANDLER)
    poke_ball_handlers = ItemHandlers::CanUseInBattle.instance_variable_get(:@add_ifs)
    ORIGINAL_POKE_BALL_HANDLER = poke_ball_handlers[:poke_balls][1]
  end
end

class Battle
  unless method_defined?(:nordeluna_ow_original_opposing_count)
    alias nordeluna_ow_original_opposing_count pbOpposingBattlerCount
  end
  def pbOpposingBattlerCount(idxBattler = 0)
    if OverworldPokemonBattles.double_capture_battle &&
       (OverworldPokemonBattles.checking_poke_ball ||
        OverworldPokemonBattles.choosing_ball_item)
      return 1
    end
    return nordeluna_ow_original_opposing_count(idxBattler)
  end

  unless method_defined?(:nordeluna_ow_original_throw_ball)
    alias nordeluna_ow_original_throw_ball pbThrowPokeBall
  end
  def pbThrowPokeBall(idxBattler, ball, catch_rate = nil, showPlayer = false)
    battler = if opposes?(idxBattler)
                @battlers[idxBattler]
              else
                @battlers[idxBattler].pbDirectOpposing(true)
              end
    battler = battler.allAllies[0] if battler&.fainted?
    target_pokemon = battler&.pokemon
    nordeluna_ow_original_throw_ball(idxBattler, ball, catch_rate, showPlayer)
    if OverworldPokemonBattles.active_battle && target_pokemon &&
       @caughtPokemon.include?(target_pokemon)
      OverworldPokemonBattles.captured_object_ids.push(target_pokemon.object_id)
    end
  end


  # Probabilidade de fuga definida pelo comportamento do encontro. Esta regra
  # so existe durante batalhas iniciadas por este plugin.
  alias nordeluna_ow_original_run pbRun unless method_defined?(:nordeluna_ow_original_run)
  def pbRun(idxBattler, duringBattle = false)
    if OverworldPokemonBattles.active_battle && !duringBattle && wildBattle? &&
       !@battlers[idxBattler].opposes?
      chance = OverworldPokemonBattles.escape_chance
      if @battleAI.pbAIRandom(100) >= chance
        pbDisplayPaused(_INTL("O Pokémon não deixou você escapar!"))
        return -1
      end
      pbSEPlay("Battle flee")
      pbDisplayPaused(_INTL("Você conseguiu escapar!"))
      @decision = 3
      return 1
    end
    return nordeluna_ow_original_run(idxBattler, duringBattle)
  end


  # Evita o seletor visual de alvo que deixa algumas interfaces customizadas
  # com a tela preta. A escolha ocorre dentro da propria janela da Mochila.
  unless method_defined?(:nordeluna_ow_original_item_menu)
    alias nordeluna_ow_original_item_menu pbItemMenu
  end
  def pbItemMenu(idxBattler, firstAction)
    return nordeluna_ow_original_item_menu(idxBattler, firstAction) if
      !OverworldPokemonBattles.double_capture_battle
    return false if !@internalBattle
    ret = false
    begin
      OverworldPokemonBattles.choosing_ball_item = true
      @scene.pbItemMenu(idxBattler, firstAction) do |item, useType, idxPkmn, idxMove, itemScene|
        next false if !item
        battler = pkmn = nil
        case useType
        when 1, 2
          next false if !ItemHandlers.hasBattleUseOnPokemon(item)
          battler = pbFindBattler(idxPkmn, idxBattler)
          pkmn = pbParty(idxBattler)[idxPkmn]
          next false if !pbCanUseItemOnPokemon?(item, pkmn, battler, itemScene)
        when 3
          next false if !ItemHandlers.hasBattleUseOnBattler(item)
          battler = pbFindBattler(idxPkmn, idxBattler)
          pkmn = battler.pokemon if battler
          next false if !pbCanUseItemOnPokemon?(item, pkmn, battler, itemScene)
        when 4
          targets = allOtherSideBattlers(idxBattler).select { |target| !target.fainted? }
          next false if targets.empty?
          if targets.length > 1
            commands = targets.map { |target| target.name }
            commands.push(_INTL("Cancelar"))
            choice = itemScene.pbShowCommands(
              _INTL("Em qual Pokémon você quer jogar a Poké Bola?"), commands
            )
            next false if choice < 0 || choice >= targets.length
            battler = targets[choice]
          else
            battler = targets[0]
          end
          idxPkmn = battler.index
          pkmn = battler.pokemon
        when 5
          battler = @battlers[idxBattler]
          pkmn = battler.pokemon
        else
          next false
        end
        next false if !pkmn
        next false if !ItemHandlers.triggerCanUseInBattle(
          item, pkmn, battler, idxMove, firstAction, self, itemScene
        )
        next false if !pbRegisterItem(idxBattler, item, idxPkmn, idxMove)
        ret = true
        next true
      end
    ensure
      OverworldPokemonBattles.choosing_ball_item = false
    end
    return ret
  end
end

ItemHandlers::CanUseInBattle.addIf(:poke_balls,
  proc { |item| GameData::Item.get(item).is_poke_ball? },
  proc { |item, pokemon, battler, move, firstAction, battle, scene, showMessages|
    original = OverworldPokemonBattles::ORIGINAL_POKE_BALL_HANDLER
    next true if !original
    begin
      OverworldPokemonBattles.checking_poke_ball = true
      next original.call(
        item, pokemon, battler, move, firstAction, battle, scene, showMessages
      )
    ensure
      OverworldPokemonBattles.checking_poke_ball = false
    end
  }
)
