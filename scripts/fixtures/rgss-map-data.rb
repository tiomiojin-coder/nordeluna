# RGSS1-compatible data objects for local RPG Maker XP map authoring.
# No graphics, file I/O or game/save execution occurs in this codec.
class Table
  attr_reader :xsize, :ysize, :zsize, :dimensions, :values
  def initialize(*sizes)
    @dimensions = sizes.length
    @xsize, @ysize, @zsize = sizes[0] || 0, sizes[1] || 1, sizes[2] || 1
    @values = Array.new(@xsize * @ysize * @zsize, 0)
  end
  def self._load(raw)
    dim, x, y, z, count = raw.unpack('V5')
    raise 'Invalid RGSS Table' unless dim.between?(1, 3) && count == x * y * z && raw.bytesize == 20 + count * 2
    table = new(*[x, y, z].first(dim))
    table.instance_variable_set(:@values, raw.byteslice(20..).unpack('v*'))
    table
  end
  def _dump(_depth = -1)
    [@dimensions, @xsize, @ysize, @zsize, @values.length].pack('V5') + @values.pack('v*')
  end
  def [](x, y = 0, z = 0); @values[(z * @ysize + y) * @xsize + x]; end
  def []=(*args)
    value = args.pop
    x, y, z = args[0], args[1] || 0, args[2] || 0
    raise 'Table write out of bounds' unless x.between?(0, @xsize-1) && y.between?(0, @ysize-1) && z.between?(0, @zsize-1) && value.between?(0, 65535)
    @values[(z * @ysize + y) * @xsize + x] = value
  end
end
class Color
  def self._load(raw); value = allocate; value.instance_variable_set(:@raw, raw); value; end
  def _dump(_depth = -1); @raw; end
end
class Tone < Color; end

module RPG
  class AudioFile
    attr_accessor :name, :volume, :pitch
    def initialize(name = '', volume = 100, pitch = 100)
      @name, @volume, @pitch = name, volume, pitch
    end
  end
  class Map
    attr_accessor :tileset_id, :width, :height, :autoplay_bgm, :bgm,
      :autoplay_bgs, :bgs, :encounter_list, :encounter_step, :data, :events
    def initialize(width, height)
      @tileset_id, @width, @height = 1, width, height
      @autoplay_bgm = @autoplay_bgs = false
      @bgm, @bgs = AudioFile.new, AudioFile.new('', 80)
      @encounter_list, @encounter_step = [], 30
      @data, @events = Table.new(width, height, 3), {}
    end
  end
  class MapInfo
    attr_accessor :name, :parent_id, :order, :expanded, :scroll_x, :scroll_y
    def initialize
      @name, @parent_id, @order = '', 0, 0
      @expanded, @scroll_x, @scroll_y = false, 0, 0
    end
  end
  class Event
    attr_accessor :id, :name, :x, :y, :pages
    def initialize(x, y)
      @id, @name, @x, @y = 0, '', x, y
      @pages = [Page.new]
    end
    class Page
      attr_accessor :condition, :graphic, :move_type, :move_speed, :move_frequency,
        :move_route, :walk_anime, :step_anime, :direction_fix, :through,
        :always_on_top, :trigger, :list
      def initialize
        @condition, @graphic = Condition.new, Graphic.new
        @move_type, @move_speed, @move_frequency = 0, 3, 3
        @move_route = MoveRoute.new
        @walk_anime, @step_anime = true, false
        @direction_fix = @through = @always_on_top = false
        @trigger, @list = 0, [EventCommand.new]
      end
      class Condition
        attr_accessor :switch1_valid, :switch2_valid, :variable_valid,
          :self_switch_valid, :switch1_id, :switch2_id, :variable_id,
          :variable_value, :self_switch_ch
        def initialize
          @switch1_valid = @switch2_valid = @variable_valid = @self_switch_valid = false
          @switch1_id = @switch2_id = @variable_id = 1
          @variable_value, @self_switch_ch = 0, 'A'
        end
      end
      class Graphic
        attr_accessor :tile_id, :character_name, :character_hue,
          :direction, :pattern, :opacity, :blend_type
        def initialize
          @tile_id, @character_name, @character_hue = 0, '', 0
          @direction, @pattern, @opacity, @blend_type = 2, 0, 255, 0
        end
      end
    end
  end
  class EventCommand
    attr_accessor :code, :indent, :parameters
    def initialize(code = 0, indent = 0, parameters = [])
      @code, @indent, @parameters = code, indent, parameters
    end
  end
  class MoveRoute
    attr_accessor :repeat, :skippable, :list
    def initialize; @repeat, @skippable, @list = true, false, [MoveCommand.new]; end
  end
  class MoveCommand
    attr_accessor :code, :parameters
    def initialize(code = 0, parameters = []); @code, @parameters = code, parameters; end
  end
  class Tileset
    attr_accessor :id, :name, :tileset_name, :autotile_names, :passages, :priorities, :terrain_tags
  end
end

def social_map_from_plan(plan)
  map = RPG::Map.new(plan.fetch('width'), plan.fetch('height'))
  map.tileset_id = plan.fetch('tileset_id')
  map.data.values.replace(plan.fetch('values'))
  if plan['bgm'] && !plan['bgm'].empty?
    map.bgm = RPG::AudioFile.new(plan['bgm'], 65)
    map.autoplay_bgm = true
  end
  plan.fetch('events').each do |row|
    event = RPG::Event.new(row.fetch('x'), row.fetch('y'))
    event.id, event.name = row.fetch('id'), row.fetch('name')
    page = event.pages[0]
    page.graphic.character_name = row.fetch('character', '')
    page.graphic.direction = row.fetch('direction', 2)
    page.trigger = row.fetch('trigger', 0)
    page.through = row.fetch('through', false)
    page.direction_fix = row.fetch('direction_fix', false)
    page.list = row.fetch('commands').map { |command| RPG::EventCommand.new(command[0], command[1], command[2]) }
    page.list << RPG::EventCommand.new unless page.list.last&.code == 0
    map.events[event.id] = event
  end
  map
end
