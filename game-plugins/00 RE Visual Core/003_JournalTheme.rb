# Shared journal language: warm paper, forest ink and quiet brass details.
module NordelunaUI
  PAPER = [237, 229, 207]
  EDGE = [202, 191, 163]
  INK = [24, 43, 42]
  FOREST = [26, 48, 45]
  DEEP = [20, 36, 35]
  LINE = [51, 73, 65]
  SELECTED = [49, 76, 62]
  SAGE = [168, 187, 157]
  GOLD = [211, 170, 96]
  CORAL = [193, 100, 79]
  ASSETS = "Plugins/00 RE Visual Core/assets/journal"

  def self.replace_constants(owner, values)
    values.each do |name, value|
      owner.send(:remove_const, name) if owner.const_defined?(name, false)
      owner.const_set(name, value)
    end
  end

  def self.surface(bmp, x, y, width, height, light)
    right = [x + width, bmp.width].min
    bottom = [y + height, bmp.height].min
    x, y = [x, 0].max, [y, 0].max
    width, height = right - x, bottom - y
    return if width <= 0 || height <= 0
    regions = bmp.instance_variable_get(:@journal_regions) || {}
    # A fully repainted panel supersedes the old contrast information below it.
    regions.delete_if { |(rx, ry, w, h), _| rx >= x && ry >= y && rx + w <= right && ry + h <= bottom }
    sequence = (bmp.instance_variable_get(:@journal_sequence) || 0) + 1
    regions[[x, y, width, height]] = [light, sequence]
    bmp.instance_variable_set(:@journal_regions, regions)
    bmp.instance_variable_set(:@journal_sequence, sequence)
  end

  def self.light_at(bmp, x, y)
    regions = bmp.instance_variable_get(:@journal_regions) || {}
    found = nil
    regions.each do |(rx, ry, w, h), value|
      next unless x >= rx && y >= ry && x < rx + w && y < ry + h
      found = value if !found || value[1] > found[1]
    end
    found&.first
  end

  def self.panel(bmp, x, y, width, height, light = false, selected = false)
    return if width <= 0 || height <= 0
    color = light ? PAPER : selected ? SELECTED : FOREST
    bmp.fill_rect(x, y, width, height, Color.new(*color))
    bmp.fill_rect(x, y + height - 1, width, 1, Color.new(*(light ? EDGE : LINE)))
    if selected
      bmp.fill_rect(x, y, 2, height, Color.new(*GOLD))
      bmp.fill_rect(x + 2, y + height - 1, [26, width - 2].min, 1, Color.new(*GOLD)) if width > 2
    end
    surface(bmp, x, y, width, height, light)
  end

  def self.background(width, height)
    bmp = Bitmap.new(width, height)
    bmp.fill_rect(0, 0, width, height, Color.new(*DEEP))
    return bmp if width < 24 || height < 24
    bmp.fill_rect(8, 8, width - 16, height - 16, Color.new(*FOREST))
    bmp.fill_rect(8, 8, 3, height - 16, Color.new(*EDGE))
    bmp.fill_rect(12, height - 9, width - 24, 2, Color.new(*EDGE))
    bmp
  end

  def self.header(bmp, title, subtitle = nil)
    REVisualTheme.draw_header_band(bmp, 12, 8, bmp.width - 24, 42)
    REPixelUI.text(bmp, title, 26, 18, 24, :ink, 0, bmp.width - 150)
    REPixelUI.text(bmp, subtitle, bmp.width - 26, 26, 16, :ink, 1, 110) if subtitle
  end

  def self.footer(bmp, hint)
    y = bmp.height - 30
    bmp.fill_rect(12, y, bmp.width - 24, 22, Color.new(*DEEP))
    surface(bmp, 12, y, bmp.width - 24, 22, false)
    REPixelUI.text(bmp, hint, bmp.width / 2, y + 6, 16, :muted, 2, bmp.width - 40)
  end

  def self.now
    Process.clock_gettime(Process::CLOCK_MONOTONIC)
  end

  def self.ease(t)
    1.0 - (1.0 - [[t, 0.0].max, 1.0].min) ** 3
  end

  def self.animate(duration)
    if duration <= 0
      yield 1.0
    elsif Process.respond_to?(:clock_gettime)
      start = now
      loop do
        progress = [[(now - start) / duration, 0.0].max, 1.0].min
        yield progress
        Graphics.update
        Input.update
        break if progress >= 1
      end
    else
      rate = Graphics.respond_to?(:frame_rate) ? Graphics.frame_rate : 60
      frames = [(duration * rate).round, 1].max
      frames.times { |i| yield((i + 1).to_f / frames); Graphics.update; Input.update }
    end
  end

  def self.transition(sprites, entering = true, duration = nil)
    values = sprites.respond_to?(:values) ? sprites.values : Array(sprites)
    originals = values.compact.reject do |s|
      s.disposed? || !s.respond_to?(:opacity) || !s.respond_to?(:y) ||
        !s.opacity.is_a?(Numeric) || !s.y.is_a?(Numeric)
    end.map do |s|
      opacity = s.opacity
      saved = s.instance_variable_get(:@journal_restore_opacity)
      opacity = saved if entering && opacity == 0 && saved
      s.instance_variable_set(:@journal_restore_opacity, opacity) unless entering
      [s, s.y, opacity]
    end
    animate(duration || (entering ? 0.22 : 0.14)) do |t|
      factor = entering ? ease(t) : 1 - t * t
      originals.each_with_index do |(sprite, y, opacity), i|
        sprite.y = (y + (1 - factor) * (sprite.z == 0 ? 0 : 10)).round
        sprite.opacity = (opacity * factor).round
      end
    end
    originals.each { |sprite, y, opacity| sprite.y = y; sprite.opacity = entering ? opacity : 0 }
  end

  def self.move_cursor(sprite, x, y)
    previous = sprite.instance_variable_get(:@journal_target)
    return if previous == [x, y]
    if previous
      sprite.instance_variable_set(:@journal_motion, [now, sprite.x, sprite.y, x, y])
    else
      sprite.x, sprite.y = x, y
    end
    sprite.instance_variable_set(:@journal_target, [x, y])
  end

  def self.tick_cursor(sprite)
    return unless sprite && !sprite.disposed?
    motion = sprite.instance_variable_get(:@journal_motion)
    return unless motion
    started, x, y, tx, ty = motion
    t = [(now - started) / 0.105, 1.0].min
    factor = ease(t)
    sprite.x = (x + (tx - x) * factor).round
    sprite.y = (y + (ty - y) * factor).round
    sprite.instance_variable_set(:@journal_motion, nil) if t >= 1
  end
end

NordelunaUI.replace_constants(REVisualTheme, {
  :BG_TOP => NordelunaUI::DEEP, :BG_MIDDLE => NordelunaUI::FOREST,
  :BG_BOTTOM => NordelunaUI::DEEP, :PANEL_TOP => NordelunaUI::FOREST,
  :PANEL_BOTTOM => NordelunaUI::FOREST, :PANEL_BG => NordelunaUI::FOREST + [255],
  :GOLD => NordelunaUI::GOLD, :GOLD_BRIGHT => NordelunaUI::GOLD,
  :GOLD_DIM => [132, 112, 74], :IVORY => NordelunaUI::PAPER,
  :TEXT => NordelunaUI::PAPER, :MUTED => NordelunaUI::SAGE,
  :CYAN => NordelunaUI::SAGE, :CORAL => NordelunaUI::CORAL,
  :SHADOW => NordelunaUI::DEEP, :LINE_COLOR => NordelunaUI::LINE + [255],
  :CURSOR_MIN => 230, :CURSOR_MAX => 255
})
NordelunaUI.replace_constants(REPixelUI, {
  :PAPER => NordelunaUI::PAPER, :INK => NordelunaUI::INK,
  :GOLD => NordelunaUI::GOLD, :NAVY => NordelunaUI::DEEP
})

module REVisualTheme
  def self.create_background(width, height)
    NordelunaUI.background(width, height)
  end

  def self.paint_panel(bmp, x, y, width, height, with_border = true)
    NordelunaUI.panel(bmp, x, y, width, height)
  end

  def self.create_cursor(width, height)
    bmp = Bitmap.new(width, height)
    return bmp if width < 3 || height < 2
    bmp.fill_rect(0, 0, 2, height, Color.new(*NordelunaUI::GOLD))
    bmp.fill_rect(2, height - 1, [26, width - 2].min, 1, Color.new(*NordelunaUI::GOLD))
    bmp
  end

  def self.draw_hline(bmp, x, y, width)
    bmp.fill_rect(x, y, width, 1, Color.new(*NordelunaUI::LINE)) if width > 0
  end

  def self.draw_header_band(bmp, x, y, width, height)
    NordelunaUI.panel(bmp, x, y, width, height, true)
    return if width < 30 || height < 16
    # A stitched spine and fabric bookmark echo the pause-menu book.
    bmp.fill_rect(x, y, 2, height, Color.new(*NordelunaUI::EDGE))
    bmp.fill_rect(x + width - 17, y, 7, [height / 3, 10].max, Color.new(*NordelunaUI::CORAL))
  end
end

module REPixelUI
  class << self
    alias journal_original_code code
    def code(char)
      symbols = { "●" => 164, "○" => 165, "♂" => 166, "♀" => 167,
                  "★" => 168, "✓" => 169, "♫" => 170, "▲" => 171, "▼" => 172 }
      symbols[char] || journal_original_code(char)
    end

    alias journal_original_image image
    alias journal_original_text text
    def image(name)
      path = "#{NordelunaUI::ASSETS}/#{name}.png"
      return journal_original_image(name) unless File.file?(path)
      key = "journal/#{name}"
      cached = @images[key]
      @images[key] = Bitmap.new(path) if !cached || cached.disposed?
      @images[key]
    end

    def text(bmp, text, x, y, size = 16, tone = :paper, align = 0, maximum = nil)
      # Text overlays and panels can share a bitmap. Resolve contrast from the
      # most recently painted surface, rather than guessing from the text colour.
      light = NordelunaUI.light_at(bmp, x, y)
      if light == true
        tone = tone == :gold ? :ochre : :ink
      elsif light == false && tone == :ink
        tone = :paper
      end
      journal_original_text(bmp, text, x, y, size, tone, align, maximum)
    end

    def tone(color)
      return :paper unless color && color.respond_to?(:red)
      return :gold if color.red > 180 && color.green > 140 && color.blue < 170
      return :ink if color.red < 65 && color.green < 70 && color.blue < 90
      return :muted if color.red < 210
      :paper
    end

    def frame(bmp, x, y, width, height, selected = false)
      NordelunaUI.panel(bmp, x, y, width, height, selected, selected)
    end
  end
end
