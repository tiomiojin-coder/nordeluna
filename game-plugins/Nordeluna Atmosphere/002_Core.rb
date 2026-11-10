module NordelunaAtmosphere
  def self.settings
    return default_settings if !$PokemonGlobal
    data = $PokemonGlobal.instance_variable_get(:@nordeluna_atmosphere)
    if !data.is_a?(Hash)
      data = default_settings
      $PokemonGlobal.instance_variable_set(:@nordeluna_atmosphere, data)
    end
    return data
  end

  def self.default_settings
    return { :enabled => DEFAULT_ENABLED, :sound => DEFAULT_SOUND,
             :density => DEFAULT_DENSITY, :maps => {} }
  end

  def self.enabled?; return settings.fetch(:enabled, DEFAULT_ENABLED); end
  def self.enabled=(value); settings[:enabled] = !!value; end
  def self.sound=(value); settings[:sound] = !!value; end
  def self.density=(value)
    settings[:density] = [[value.to_f, 0.0].max, 1.0].min
  end

  # Persistent, per-map event override. :auto removes it.
  def self.set(profile, map_id = nil)
    profile = profile.to_sym
    raise ArgumentError, "Unknown atmosphere: #{profile}" if profile != :auto && !PROFILES.key?(profile)
    map_id ||= $game_map.map_id
    maps = (settings[:maps] ||= {})
    profile == :auto ? maps.delete(map_id) : maps[map_id] = profile
  end

  def self.read_project_profiles(text)
    profiles = {}
    text.each_line do |line|
      match = line.strip.match(/\A\s*(\d+)\s*=\s*(\w+)\s*(?:#.*)?\z/)
      next if !match
      id, profile = match[1].to_i, match[2].downcase.to_sym
      profiles[id] = profile if id > 0 && PROFILES.key?(profile)
    end
    return profiles
  end

  def self.project_profiles(reload = false)
    if reload || !@project_profiles
      @project_profiles = File.file?(PROJECT_FILE) ? read_project_profiles(File.read(PROJECT_FILE)) : {}
    end
    return @project_profiles
  end

  # Stores map defaults with the plugin, for new games and existing saves that
  # have no event override. Atomic replacement keeps the previous file on error.
  def self.set_project(profile, map_id = nil)
    profile = profile.to_sym
    raise ArgumentError, "Unknown atmosphere: #{profile}" if profile != :auto && !PROFILES.key?(profile)
    map_id = (map_id || $game_map.map_id).to_i
    raise ArgumentError, 'Map ID must be positive' if map_id <= 0
    profiles = project_profiles(true).dup
    profile == :auto ? profiles.delete(map_id) : profiles[map_id] = profile
    content = "# Project map defaults. Format: map_id = profile\n"
    profiles.keys.sort.each { |id| content += "#{id} = #{profiles[id]}\n" }
    temporary = "#{PROJECT_FILE}.tmp"
    begin
      File.open(temporary, 'wb') { |file| file.write(content); file.flush; file.fsync }
      File.rename(temporary, PROJECT_FILE)
    ensure
      File.delete(temporary) if File.file?(temporary)
    end
    @project_profiles = profiles
    set(:auto, map_id) # Display the new default in this save too.
  end

  def self.profile_for(map)
    return :off if !map || !enabled?
    overrides = settings[:maps] || {}
    return overrides[map.map_id] if PROFILES.key?(overrides[map.map_id])
    project = project_profiles
    return project[map.map_id] if project.key?(map.map_id)
    metadata = map.metadata
    if metadata
      metadata.flags.each do |flag|
        match = flag.match(/\AAtmosphere:(\w+)\z/i)
        next if !match
        profile = match[1].downcase.to_sym
        return profile if PROFILES.key?(profile)
      end
    end
    return MAP_PROFILES[map.map_id] if MAP_PROFILES.key?(map.map_id)
    return :caverna if metadata&.dark_map
    return :off if !metadata&.outdoor_map
    # No name guessing: an unknown outdoor map gets only a light breeze.
    return :campo
  end

  def self.night_strength
    time = pbGetTimeNow
    return 1.0 if PBDayNight.isNight?(time)
    # getShade is a noon-centred gradient, not the game's day/night boundary.
    # Fade out after sunrise (05-07h) and in before night starts (17-20h).
    hour = time.hour + time.min / 60.0
    strength = hour < 12 ? (7.0 - hour) / 2.0 : (hour - 17.0) / 3.0
    return [[strength, 0.0].max, 1.0].min
  end

  def self.weather_category
    return GameData::Weather.get($game_screen.weather_type).category
  end

  def self.dark?
    return true if $game_map.metadata&.dark_map
    return defined?(NordelunaLight) && $game_switches &&
           $game_switches[NordelunaLight::SWITCH_ESCURO]
  end

  def self.state(map = $game_map)
    profile = profile_for(map)
    data = PROFILES.fetch(profile)
    category = weather_category
    night = night_strength
    wet = [:Rain, :Hail, :Sandstorm].include?(category)
    kind = data[:particle]
    if [:campo, :mata].include?(profile) && night > 0.5 && !wet
      kind = :firefly
    end
    count = (data[:count] * settings.fetch(:density, DEFAULT_DENSITY)).round
    count = 0 if wet
    sound = data[:sound]
    sound = :night if night > 0.5 && [:campo, :sertao, :mata, :cidade].include?(profile)
    sound = :rain if category == :Rain && profile != :off
    sound = :wind if [:Hail, :Sandstorm].include?(category) && profile != :off
    sound = nil if !settings.fetch(:sound, DEFAULT_SOUND)
    fog = [:Fog, :Rain, :Hail, :Sandstorm].include?(category) ? 0 : data[:fog]
    # Existing Essentials tint and lantern remain responsible for darkness.
    warm = profile == :sertao && category == :None && !dark? ? (9 * (1 - night)).round : 0
    rays = [:mata, :ruinas].include?(profile) && category == :None && !dark? ?
           (profile == :mata ? 38 * (1 - night) : 18 * night).round : 0
    return { :profile => profile, :particle => kind, :count => [count, MAX_PARTICLES].min,
             :fog => fog, :sound => sound, :warm => warm, :night => night, :rays => rays }
  end

  # Use the BGS channel only while it belongs to this plugin or is initially empty.
  # An event stopping/replacing our BGS reserves the channel until the next map.
  class Soundscape
    def owned?(audio)
      return audio && audio.name.start_with?(AUDIO_PREFIX)
    end

    # Keep compatibility with existing events without starting ambient audio.
    def update(sound, map_id)
      stop
    end

    def stop
      if $game_system && owned?($game_system.playing_bgs)
        $game_system.bgs_stop
      end
      @last_name = nil
    end
  end
end
