#===============================================================================
# Musica suave durante vozes e modo assistir. Pokemon Essentials 21.1 / mkxp-z.
# O ganho de BGM e temporario: nao altera bgmvolume nem reinicia a trilha.
#===============================================================================
class PokemonSystem
  def nordeluna_voice_music
    return 35 if @nordeluna_voice_music.nil?
    return [[@nordeluna_voice_music.to_i, 0].max, 100].min
  end

  def nordeluna_voice_music=(value)
    @nordeluna_voice_music = [[value.to_i, 0].max, 100].min
  end

  def nordeluna_voice_watch
    return @nordeluna_voice_watch == 1 ? 1 : 0
  end

  def nordeluna_voice_watch=(value)
    @nordeluna_voice_watch = value.to_i == 1 ? 1 : 0
  end

  def nordeluna_voice_pause
    return 400 if @nordeluna_voice_pause.nil?
    return [[@nordeluna_voice_pause.to_i, 0].max, 2000].min
  end

  def nordeluna_voice_pause=(value)
    @nordeluna_voice_pause = [[value.to_i, 0].max, 2000].min
  end
end

MenuHandlers.add(:options_menu, :nordeluna_voice_music, {
  "name" => _INTL("Música na dublagem"), "order" => 26,
  "type" => SliderOption, "parameters" => [0, 100, 5],
  "description" => _INTL("Porcentagem da música durante as vozes. 100 mantém o volume normal."),
  "get_proc" => proc { next $PokemonSystem.nordeluna_voice_music },
  "set_proc" => proc { |value, _scene| $PokemonSystem.nordeluna_voice_music = value }
})
MenuHandlers.add(:options_menu, :nordeluna_voice_watch, {
  "name" => _INTL("Modo assistir"), "order" => 27,
  "type" => EnumOption, "parameters" => [_INTL("Desligado"), _INTL("Ligado")],
  "description" => _INTL("Avança o diálogo depois da gravação. Escolhas continuam manuais."),
  "get_proc" => proc { next $PokemonSystem.nordeluna_voice_watch },
  "set_proc" => proc { |value, _scene| $PokemonSystem.nordeluna_voice_watch = value }
})
MenuHandlers.add(:options_menu, :nordeluna_voice_pause, {
  "name" => _INTL("Pausa das falas (ms)"), "order" => 28,
  "type" => SliderOption, "parameters" => [0, 2000, 100],
  "description" => _INTL("Pausa entre falas no modo assistir, em milissegundos."),
  "get_proc" => proc { next $PokemonSystem.nordeluna_voice_pause },
  "set_proc" => proc { |value, _scene| $PokemonSystem.nordeluna_voice_pause = value }
})

module NordelunaVoice
  TIMINGS = "Data/Dublagem/durations.tsv"
  DUCK_ATTACK = 0.20
  DUCK_RELEASE = 0.55
  PAGE_PAUSE = 0.85

  class << self
    def clock
      return Process.clock_gettime(Process::CLOCK_MONOTONIC)
    end

    def watch_mode?
      return @watch_override unless @watch_override.nil?
      return $PokemonSystem && $PokemonSystem.nordeluna_voice_watch == 1
    end

    def with_watch_mode(enabled)
      previous = @watch_override
      @watch_override = !!enabled
      return yield
    ensure
      @watch_override = previous
    end

    def watch_pause
      return $PokemonSystem ? $PokemonSystem.nordeluna_voice_pause / 1000.0 : 0.4
    end

    def music_gain
      return $PokemonSystem ? $PokemonSystem.nordeluna_voice_music / 100.0 : 0.35
    end

    def reload_timings!
      @duration_cache = {}
      @timings = {}
      return if !File.file?(TIMINGS)
      File.foreach(TIMINGS, :encoding => "UTF-8") do |line|
        name, seconds = line.chomp.split("\t", 2)
        next if !name || name.start_with?("#") || !seconds
        value = Float(seconds) rescue 0
        @timings[name] = value if value.finite? && value > 0
      end
    rescue StandardError => error
      warn_debug("Duracoes indisponiveis: #{error.message}")
    end

    def audio_duration(path)
      reload_timings! if !@duration_cache
      key = path.to_s.tr("\\", "/")
      return @duration_cache[key] if @duration_cache.key?(key)
      relative = key.sub(/\A.*?Audio\/SE\/FALAS\//i, "")
      seconds = @timings[relative]
      seconds ||= getPlayTime(path).to_f if defined?(getPlayTime)
      seconds = nil if !seconds || !seconds.finite? || seconds <= 0
      @duration_cache[key] = seconds
      return seconds
    rescue StandardError => error
      warn_debug("Nao foi possivel medir #{path}: #{error.message}")
      return nil
    end

    def voice_started(path, pitch)
      duration = audio_duration(path)
      @last_playback = { :ends_at => duration ? clock + duration * 100.0 / pitch : nil }
      (@playbacks ||= []) << @last_playback if duration
      return @last_playback
    rescue StandardError => error
      # Uma falha nos recursos opcionais nunca transforma um audio tocado em
      # falha de reproducao nem deixa a musica permanentemente reduzida.
      warn_debug("Sincronizacao indisponivel: #{error.message}")
      return nil
    end

    def playback_active?(playback)
      return false if !playback
      return !playback[:ends_at] || clock < playback[:ends_at]
    end

    def voices_stopped
      (@playbacks || []).each { |playback| playback[:ends_at] = clock }
      @playbacks = []
    end

    def begin_message(window, voice, args, text, playing)
      if !voice || voice[:audio].to_s.empty?
        context = { :window => window, :previous => @watch_context, :automatic => false }
        @watch_context = context
        return context
      end
      playback = playing ? @last_playback : nil
      file = audio_name(voice[:audio])
      path = file ? pbResolveAudioSE(file) : nil
      duration = path ? audio_duration(path) : nil
      pitch = [[voice[:pitch].to_i, 50].max, 150].min
      # Escolhas e comandos especiais de auto-fechamento mantem o controle do
      # Essentials. Nunca geramos um confirmar dentro da lista de respostas.
      automatic = watch_mode? && duration && args[0] != false && !args[1]
      automatic &&= !text.match?(/\\(?:ch\[|wtnp\[|\^|cl(?:\[|\b))/i)
      context = { :window => window, :previous => @watch_context,
                  :playback => playback, :automatic => automatic,
                  :ends_at => clock + (duration || 0) * 100.0 / pitch }
      if playback && !playback[:ends_at]
        (@playbacks ||= []) << playback
        context[:message_only] = true
      end
      @watch_context = context
      return context
    end

    def end_message(context)
      @watch_context = context[:previous]
      if context[:message_only]
        @playbacks.delete(context[:playback]) if @playbacks
      end
    end

    def watching?
      return @watch_context && @watch_context[:automatic] && !@watch_context[:consumed]
    end

    def watch_confirm?
      return false if !watching?
      context = @watch_context
      window = context[:window]
      now = clock
      return false if window.respond_to?(:disposed?) && window.disposed?
      return false if window.waitcount > 0
      if window.busy?
        context.delete(:text_ready)
        if window.pausing?
          context[:page_ready] ||= now + PAGE_PAUSE
          if now >= context[:page_ready]
            context.delete(:page_ready)
            return true
          end
        else
          context.delete(:page_ready)
        end
        return false
      end
      context[:text_ready] ||= now
      ended = context[:playback] ? context[:playback][:ends_at] : context[:ends_at]
      return false if !ended || now < [ended, context[:text_ready]].max + watch_pause
      context[:consumed] = true
      return true
    end

    def update_cinematics
      @playbacks ||= []
      now = clock
      @playbacks.reject! { |playback| playback[:ends_at] && now >= playback[:ends_at] }
      return if @playbacks.empty? && !@duck_base
      # bgm_volume sem indice representa o ganho global de BGM no mkxp-z.
      # Ao usar esse ganho, fades, trocas de faixa e o slider BGM continuam livres.
      return if !Audio.respond_to?(:bgm_volume) || !Audio.respond_to?(:bgm_set_volume)
      if !@duck_base
        @duck_base = Audio.bgm_volume.to_f
        @duck_ratio = 1.0
        @duck_target = nil
      end
      target = @playbacks.empty? ? 1.0 : music_gain
      if target != @duck_target
        @duck_from = @duck_ratio
        @duck_target = target
        @duck_since = now
        @duck_duration = target < @duck_ratio ? DUCK_ATTACK : DUCK_RELEASE
      end
      progress = [[(now - @duck_since) / @duck_duration, 0.0].max, 1.0].min
      @duck_ratio = @duck_from + (target - @duck_from) * progress
      value = (@duck_base * @duck_ratio).round
      if value != @duck_applied
        Audio.bgm_set_volume(value)
        @duck_applied = value
      end
      if @playbacks.empty? && @duck_ratio >= 1.0
        @duck_base = @duck_applied = @duck_target = @duck_since = nil
      end
    rescue StandardError => error
      warn_debug("Reducao de musica indisponivel: #{error.message}")
      reset_cinematics!
    end

    def reset_cinematics!
      Audio.bgm_set_volume(@duck_base.round) if @duck_base && Audio.respond_to?(:bgm_set_volume)
    rescue StandardError => error
      warn_debug("Restauracao da musica indisponivel: #{error.message}")
    ensure
      @duck_base = @duck_applied = @duck_target = @duck_since = nil
      @playbacks = []
      @watch_context = nil
    end
  end

  module CinematicFrames
    def update(*args)
      result = super
      NordelunaVoice.update_cinematics
      return result
    rescue Exception
      NordelunaVoice.reset_cinematics!
      raise
    end
  end

  module CinematicInput
    def trigger?(key)
      actual = super
      return actual if actual || key != Input::USE || !NordelunaVoice.watching?
      # Limita o confirmar sintetico ao loop de texto, sem afetar mapa, menus,
      # blocos de evento ou janelas de escolhas que tambem consultam Input::USE.
      caller = caller_locations(1, 1)[0]
      return false if !caller || caller.base_label != "pbMessageDisplay"
      return NordelunaVoice.watch_confirm?
    end
  end

  module CinematicSEStop
    def se_stop(*args)
      result = super
      NordelunaVoice.voices_stopped
      return result
    end
  end
end

Graphics.singleton_class.prepend(NordelunaVoice::CinematicFrames)
Input.singleton_class.prepend(NordelunaVoice::CinematicInput)
Audio.singleton_class.prepend(NordelunaVoice::CinematicSEStop)
