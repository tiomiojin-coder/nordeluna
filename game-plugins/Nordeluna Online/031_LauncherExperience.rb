# Local launcher contract shared by PC/Android. Never downloads Ruby code.
module NordelunaOnline
  module LauncherExperience
    class << self
      def config
        return @config if @config
        file=File.join(Dir.pwd,'.nordeluna-launcher.json')
        value=File.file?(file) && File.size(file)<=8192 ? JSON.parse(File.binread(file)) : {}
        @config=value.is_a?(Hash) ? value : {}
      rescue StandardError
        @config={}
      end
      def channel; config['channel']=='testers' ? 'testers' : 'stable'; end
      def save_root
        value=config['save_root']
        return nil unless value.is_a?(String) && !value.empty? && !value.include?("\0")
        root=File.expand_path(value)
        ContentUpdates.mkdir(root)
        root
      end
      def metadata
        directory=save_root
        return unless directory
        seconds=defined?($stats) && $stats && $stats.respond_to?(:play_time) ? $stats.play_time.to_i : 0
        ContentUpdates.write_json(File.join(directory,'launcher-save-info.json'),
          {'saved_at'=>Time.now.utc.to_s,'play_seconds'=>seconds,'channel'=>channel,'build'=>NordelunaOnline.build})
      rescue StandardError => error
        NordelunaOnline.record_online_error(error,'launcher_metadata')
      end
      def apply_options
        return unless defined?($PokemonSystem) && $PokemonSystem
        volume=config['volume']
        if volume.is_a?(Integer) && volume.between?(0,100)
          $PokemonSystem.bgmvolume=volume if $PokemonSystem.respond_to?(:bgmvolume=)
          $PokemonSystem.sevolume=volume if $PokemonSystem.respond_to?(:sevolume=)
        end
      end
      def migrate_legacy
        target=save_root
        return unless target && channel=='stable' && defined?(REInterface)
        original=REInterface.save_directory
        return if File.expand_path(original)==target || Dir.glob(File.join(target,'*.rxdata')).any?
        rows=Dir.glob(File.join(original,'*')).select do |file|
          File.file?(file) && File.basename(file).match?(/\A(?:Save_\d+\.(?:rxdata|preview)|last_slot\.dat|Game\.rxdata)\z/i)
        end
        # Copy without removing originals. No Marshal loading or save conversion.
        rows.each do |file|
          destination=File.join(target,File.basename(file))
          ContentUpdates.atomic_write(destination,File.binread(file)) unless File.file?(destination)
        end
      end
    end
  end
  module LauncherBuild
    def build
      result=super
      LauncherExperience.channel=='testers' ? result+'-testers' : result
    end
    def request(url,data)
      data=data.merge('channel'=>LauncherExperience.channel)
      if LauncherExperience.channel=='testers'
        raise Error,'O canal de testes exige o servidor oficial.' unless ['https://nordeluna-online.discloud.dev','https://nordeluna-online.discloud.dev/api'].include?(url)
        data['tester']=LauncherExperience.config['tester']
      end
      super(url,data)
    rescue Error => error
      if error.message.match?(/versoes do jogo sao diferentes|Build.*incompativel/i)
        raise VersionMismatch,'PC e Android precisam da mesma versao do jogo e canal. Atualize antes de batalhar ou trocar.'
      end
      raise
    end
  end
  singleton_class.prepend(LauncherBuild)
  module LauncherSaveDirectory
    def save_directory
      LauncherExperience.save_root || super
    end
  end
  LauncherExperience.migrate_legacy
  REInterface.singleton_class.prepend(LauncherSaveDirectory) if defined?(REInterface)
  module LauncherSaveMetadata
    def save(*args, **kwargs)
      result=super
      LauncherExperience.metadata if result
      result
    end
    def load(*args, **kwargs)
      result=super
      LauncherExperience.apply_options
      result
    end
  end
  Game.singleton_class.prepend(LauncherSaveMetadata)
  if LauncherExperience.save_root && defined?(SaveData::FILE_PATH)
    SaveData.send(:remove_const,:FILE_PATH)
    SaveData.const_set(:FILE_PATH,File.join(LauncherExperience.save_root,'Game.rxdata'))
  end
end
if NordelunaOnline::LauncherExperience.config['settings_only']==true && defined?(System) && System.respond_to?(:show_settings)
  System.show_settings
  exit
end
EventHandlers.add(:on_frame_update,:nordeluna_launcher_preferences,proc do
  unless $nordeluna_launcher_ready
    NordelunaOnline::LauncherExperience.apply_options
    $nordeluna_launcher_ready=true if defined?($PokemonSystem) && $PokemonSystem
  end
end)
