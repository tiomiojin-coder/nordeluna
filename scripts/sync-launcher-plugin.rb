# Build staging only. Keep the executable plugin bundle and source in agreement.
require 'zlib'
game, source = ARGV
raise 'Expected extracted game and launcher source' unless game && source
text=File.binread(source).force_encoding('UTF-8')
RubyVM::InstructionSequence.compile(text)
file=File.join(game,'Data','PluginScripts.rxdata')
bundle=Marshal.load(File.binread(file))
others=Marshal.dump(bundle.reject { |entry| entry[0]=='Nordeluna Online' })
plugins=bundle.select { |entry| entry[0]=='Nordeluna Online' }
raise 'Online plugin absent or duplicated' unless plugins.length==1
rows=plugins[0][2].select { |row| row[0].end_with?('031_LauncherExperience.rb') }
raise 'Launcher script absent or duplicated' unless rows.length==1
rows[0][1]=Zlib::Deflate.deflate(text)
raise 'Another plugin changed' unless others==Marshal.dump(bundle.reject { |entry| entry[0]=='Nordeluna Online' })
File.binwrite(file+'.tmp',Marshal.dump(bundle))
File.rename(file+'.tmp',file)
File.binwrite(File.join(game,'Plugins','Nordeluna Online','031_LauncherExperience.rb'),text)
puts 'Launcher tester access integrated into compiled plugin bundle'
