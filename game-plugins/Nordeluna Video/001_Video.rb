#===============================================================================
# Videos MP4 com audio: player Windows no PC e player nativo no port Android.
# No evento: pbVideo("001")
# Usa o arquivo original e o FFplay portatil incluido no plugin.
#===============================================================================
module NordelunaVideo
  DIRECTORIES = ["Movies", "Plugins/Nordeluna Video/movies"]

  def self.android?
    return true if defined?(System) && System.respond_to?(:is_android?) && System.is_android?
    RUBY_PLATFORM.include?("android")
  end

  def self.clock
    Process.clock_gettime(Process::CLOCK_MONOTONIC)
  end

  def self.report(message)
    pbMessage(message)
    return false
  end

  def self.resolve(name)
    name = name.to_s.tr("\\", "/").sub(/\AMovies\//i, "")
    return nil if name.empty? || name.split("/").include?("..")
    extension = File.extname(name)
    return nil if !extension.empty? && extension.downcase != ".mp4"
    name += ".mp4" if extension.empty?
    return DIRECTORIES.map { |directory| "#{directory}/#{name}" }.find { |path| File.file?(path) }
  end

  # bgm_pause guarda a posicao, mas nao interrompe o som sem fade.
  # BGS usa a pausa normal do Essentials, inclusive os ambientes do Nordeluna.
  def self.pause_audio(state, options)
    system = $game_system
    return if !system
    state[:system] = system
    if options[:bgm] == :pausar && !system.instance_variable_get(:@bgm_paused)
      state[:bgm] = system.playing_bgm&.clone
      system.bgm_pause
      state[:resume_bgm] = true
      Audio.bgm_stop
    end
    if options[:bgs] == :pausar && !system.instance_variable_get(:@bgs_paused)
      state[:bgs] = system.playing_bgs&.clone
      state[:resume_bgs] = true
      system.bgs_pause
    end
    Audio.me_stop
    Audio.se_stop
  end

  def self.resume_audio(state)
    system = state[:system]
    return if !system
    begin
      system.bgm_resume(state[:bgm]) if state[:resume_bgm]
    ensure
      system.bgs_resume(state[:bgs]) if state[:resume_bgs]
    end
  end

  def self.wait_seconds(seconds)
    deadline = clock + seconds
    while clock < deadline
      Graphics.update
      Input.update
    end
  end

  def self.fade_brightness(target, seconds)
    original = Graphics.brightness
    if seconds > 0 && original != target
      started = clock
      loop do
        ratio = [[(clock - started) / seconds, 0.0].max, 1.0].min
        Graphics.brightness = (original + (target - original) * ratio).round
        break if ratio >= 1.0
        Graphics.update
        Input.update
      end
    end
    Graphics.brightness = target
  end

  def self.play(name, volume = nil, skippable = nil, overrides = {})
    return false if @playing
    extension = File.extname(name.to_s)
    if !extension.empty? && extension.downcase != ".mp4"
      return report("Use o arquivo MP4 original com pbVideo, por exemplo: pbVideo(\"001\").")
    end
    path = resolve(name)
    return report("Video nao encontrado: #{name}. Coloque o MP4 na pasta Movies do jogo.") if !path
    options = Settings.resolve(name, volume, skippable, overrides)
    player = android? ? AndroidPlayer : WindowsPlayer
    options[:duracao] ||= MovieInfo.duration(path) if !android? && options[:saida] > 0
    volume = options[:audio] == :mudo ? 0 : options[:volume]
    volume = (volume * $PokemonSystem.sevolume / 100.0).round if $PokemonSystem
    state = {}
    original_brightness = Graphics.brightness
    completed = false
    @playing = true
    begin
      pause_audio(state, options)
      fade_brightness(0, options[:entrada])
      wait_seconds(options[:pausa_antes])
      Input.update
      player.play(path, volume, options[:pular], options)
      wait_seconds(options[:pausa_depois])
      completed = true
      return true
    ensure
      begin
        resume_audio(state)
      ensure
        begin
          fade_brightness(original_brightness, options[:saida]) if completed
        ensure
          Graphics.brightness = original_brightness
          @playing = false
          Input.update
          Graphics.frame_reset
        end
      end
    end
  rescue StandardError => error
    echoln "[Nordeluna Video] #{error.class}: #{error.message}"
    return report("Nao foi possivel reproduzir o MP4. #{error.message}")
  end
end

def pbVideo(name, volume = nil, skippable = nil, options = {})
  return NordelunaVideo.play(name, volume, skippable, options)
end
