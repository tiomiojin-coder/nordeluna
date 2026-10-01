# Run with: ruby android/tests/display_preload_test.rb
module Settings
  SCREEN_WIDTH = 512
  SCREEN_HEIGHT = 384
end

module Graphics
  class << self
    attr_accessor :fullscreen
    attr_reader :resizes

    def resize_screen(w, h)
      (@resizes ||= []) << [w, h]
    end

    def scale=(_value)
      raise "Desktop scaling reached the Android renderer"
    end

    def center
      raise "Desktop window positioning reached the Android renderer"
    end
  end
end

preload = File.expand_path("../nordeluna-display.rb", __dir__)
load preload

# Simulate Essentials defining the routine AFTER the engine loads the preload.
def pbSetResizeFactor(factor)
  Graphics.fullscreen = false
  Graphics.scale = (factor + 1) * 0.5
  Graphics.center
end

[-1, 0, 1, 2, 3, 4].each do |factor|
  Graphics.fullscreen = false
  pbSetResizeFactor(factor)
  raise "Lost fullscreen for #{factor}" unless Graphics.fullscreen
end
raise "Logical game resolution changed" unless Graphics.resizes == [[512, 384]]

# A second load must not duplicate the hook; resets must still initialize RGSS.
load preload
$ResizeInitialized = false
pbSetResizeFactor(1)
raise "Reset failed" unless Graphics.resizes == [[512, 384], [512, 384]]
raise "Duplicate preload" unless Object.ancestors.count(NordelunaAndroidDisplay) == 1
puts "Android resize hook: desktop factors, reset and repeated load passed"
