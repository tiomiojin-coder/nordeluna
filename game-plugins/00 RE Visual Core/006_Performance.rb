# Device-local preferences, shared with the Android settings panel. Never part
# of a save, a game archive, or the online account/party data.
module NordelunaPerformance
  KEYS = %w[particles shadows decorations].freeze
  LABELS = ["Desligado", "Reduzido", "Normal"].freeze
  class << self
    def path; File.join(Dir.pwd, ".nordeluna-performance.cfg"); end
    def reload(force=false)
      now=Process.clock_gettime(Process::CLOCK_MONOTONIC)
      return if !force && now<(@next_check || 0)
      @next_check=now+1
      signature=File.file?(path) ? [path,File.mtime(path).to_f,File.size(path)] : [path,nil]
      return if !force && @values && signature==@signature
      values=KEYS.to_h { |key| [key,2] }
      if File.file?(path) && File.size(path)<=1024
        lines=File.binread(path).split(/\r?\n/)
        if lines.include?("version=1")
          lines.each do |line|
            key,value=line.split("=",2)
            values[key]=value.to_i if KEYS.include?(key) && value && value.match?(/\A[012]\z/)
          end
        end
      end
      @values,@signature=values,signature
    rescue SystemCallError,IOError
      @values ||= KEYS.to_h { |key| [key,2] }
    end
    def level(key)
      reload
      (@values || {})[key.to_s] || 2
    end
    def set(key,value)
      key=key.to_s
      return false unless KEYS.include?(key) && value.is_a?(Integer) && value.between?(0,2)
      reload(true)
      previous=@values.dup
      @values[key]=value
      text="version=1\n"+KEYS.map { |name| "#{name}=#{@values[name]}\n" }.join
      File.binwrite(path+".tmp",text)
      File.rename(path+".tmp",path)
      @signature=nil;@next_check=0
      true
    rescue SystemCallError,IOError
      @values=previous if previous
      false
    end
    def particles(count)
      case level(:particles)
      when 0 then 0
      when 1 then [(count/3.0).ceil,6].min
      else count
      end
    end
    def decoration_step?(number)
      mode=level(:decorations)
      mode==2 || (mode==1 && number.even?)
    end
    def open
      loop do
        choice=pbMessage(_INTL("Efeitos neste aparelho\nParticulas: {1}\nSombras: {2}\nDecoracao: {3}",
          LABELS[level(:particles)],LABELS[level(:shadows)],LABELS[level(:decorations)]),
          [_INTL("Particulas"),_INTL("Sombras projetadas"),_INTL("Efeitos decorativos"),_INTL("Restaurar normal"),_INTL("Voltar")],5)
        break unless choice.between?(0,3)
        if choice==3
          results=KEYS.map { |key| set(key,2) }
          pbMessage(_INTL("Nao foi possivel salvar todas as preferencias neste aparelho.")) unless results.all?
          next
        end
        help=choice==1 ? "Reduzido mantem apenas a sombra projetada do jogador." :
             choice==2 ? "Controla nevoa, raios de luz, brilhos ambientais e marcas no barro." :
             "Controla a quantidade de folhas, poeira, polen e outras particulas do ambiente."
        selected=pbMessage(_INTL(help),LABELS.map { |label| _INTL(label) }+[_INTL("Voltar")],4)
        if selected.between?(0,2) && !set(KEYS[choice],selected)
          pbMessage(_INTL("Nao foi possivel salvar esta preferencia neste aparelho."))
        end
      end
    end
  end
end

MenuHandlers.add(:pause_menu,:nordeluna_performance,{
  "name"=>_INTL("Desempenho"),"order"=>60,
  "condition"=>proc { $game_temp && !$game_temp.in_battle },
  "effect"=>proc { |menu|
    menu.pbHideMenu
    begin
      NordelunaPerformance.open
    ensure
      menu.pbShowMenu
    end
    next false
  }
})
