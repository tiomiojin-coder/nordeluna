#===============================================================================
# Nordeluna - papel antigo. Shared presentation only; no save-data changes.
# Paper texture generated with OpenAI imagegen; pixel typography is code-native.
#===============================================================================
module NordelunaUI
  replace_constants(self, {
    :PAPER => [245, 227, 183], :EDGE => [183, 143, 86],
    :INK => [66, 43, 28], :FOREST => [238, 217, 171],
    :DEEP => [69, 43, 29], :LINE => [195, 164, 113],
    :SELECTED => [222, 195, 142], :SAGE => [112, 83, 52],
    :GOLD => [138, 85, 35], :CORAL => [166, 76, 50]
  })
  BOOK_ASSETS = "Plugins/00 RE Visual Core/assets/book"

  def self.parchment
    return @book_parchment if @book_parchment && !@book_parchment.disposed?
    source = Bitmap.new("#{BOOK_ASSETS}/parchment.png")
    @book_parchment = Bitmap.new(512, 384)
    @book_parchment.stretch_blt(Rect.new(0, 0, 512, 384), source,
                                Rect.new(0, 0, source.width, source.height))
    source.dispose
    @book_parchment
  end

  def self.paper(bmp, x, y, width, height, selected = false)
    return if width <= 0 || height <= 0
    texture = parchment
    bmp.stretch_blt(Rect.new(x, y, width, height), texture,
                    Rect.new(0, 0, texture.width, texture.height))
    if selected
      wash = Bitmap.new(1, 1)
      wash.fill_rect(0, 0, 1, 1, Color.new(123, 77, 25, 28))
      bmp.stretch_blt(Rect.new(x, y, width, height), wash, Rect.new(0, 0, 1, 1))
      wash.dispose
    end
    surface(bmp, x, y, width, height, true)
  end

  def self.panel(bmp, x, y, width, height, light = false, selected = false)
    return if width <= 0 || height <= 0
    paper(bmp, x, y, width, height, selected)
    edge = Color.new(*EDGE, 150)
    bmp.fill_rect(x, y + height - 1, width, 1, edge)
    if selected
      bmp.fill_rect(x, y, 2, height, Color.new(*GOLD))
      bmp.fill_rect(x + 2, y + height - 1, [26, width - 2].min, 1, Color.new(*GOLD)) if width > 2
    end
  end

  def self.background(width, height)
    bmp = Bitmap.new(width, height)
    bmp.fill_rect(0, 0, width, height, Color.new(*DEEP))
    return bmp if width < 24 || height < 24
    # Leather cover, stacked page edges, then the actual writing surface.
    bmp.fill_rect(5, 5, width - 10, height - 10, Color.new(104, 65, 38))
    bmp.fill_rect(8, 8, width - 16, height - 15, Color.new(*EDGE))
    paper(bmp, 10, 8, width - 20, height - 20)
    bmp.fill_rect(10, height - 10, width - 22, 1, Color.new(220, 194, 143))
    bmp.fill_rect(10, height - 8, width - 24, 1, Color.new(157, 113, 64))
    bmp.fill_rect(12, 11, width - 24, 1, Color.new(*EDGE, 120))
    # Small stitched binding, kept inside the otherwise unused margin.
    (22...(height - 24)).step(17) do |y|
      bmp.fill_rect(7, y, 3, 1, Color.new(220, 189, 133))
    end
    bmp
  end

  def self.footer(bmp, hint)
    y = bmp.height - 30
    paper(bmp, 12, y, bmp.width - 24, 22)
    bmp.fill_rect(20, y, bmp.width - 40, 1, Color.new(*EDGE, 140))
    REPixelUI.text(bmp, hint, bmp.width / 2, y + 7, 16, :muted, 2, bmp.width - 40)
  end
end

NordelunaUI.replace_constants(REVisualTheme, {
  :BG_TOP => NordelunaUI::DEEP, :BG_MIDDLE => NordelunaUI::PAPER,
  :BG_BOTTOM => NordelunaUI::DEEP, :PANEL_TOP => NordelunaUI::PAPER,
  :PANEL_BOTTOM => NordelunaUI::FOREST, :PANEL_BG => NordelunaUI::PAPER + [255],
  :GOLD => NordelunaUI::GOLD, :GOLD_BRIGHT => NordelunaUI::GOLD,
  :GOLD_DIM => NordelunaUI::EDGE, :IVORY => NordelunaUI::INK,
  :TEXT => NordelunaUI::INK, :MUTED => NordelunaUI::SAGE,
  :CYAN => NordelunaUI::SAGE, :CORAL => NordelunaUI::CORAL,
  :SHADOW => NordelunaUI::PAPER, :LINE_COLOR => NordelunaUI::LINE + [180]
})
NordelunaUI.replace_constants(REPixelUI, {
  :PAPER => NordelunaUI::PAPER, :INK => NordelunaUI::INK,
  :GOLD => NordelunaUI::GOLD, :NAVY => NordelunaUI::DEEP
})

module REPixelUI
  class << self
    alias aged_book_image image
    def image(name)
      if name == "background"
        cached = @images["book/background"]
        @images["book/background"] = NordelunaUI.background(512, 384) if !cached || cached.disposed?
        return @images["book/background"]
      end
      path = "#{NordelunaUI::BOOK_ASSETS}/#{name}.png"
      return aged_book_image(name) unless File.file?(path)
      key = "book/#{name}"
      cached = @images[key]
      @images[key] = Bitmap.new(path) if !cached || cached.disposed?
      @images[key]
    end

    def text(bmp, text, x, y, size = 16, tone = :paper, align = 0, maximum = nil)
      # A separate text sprite has no surface map. Both journal pages are paper,
      # so resolve contrast explicitly instead of inheriting the former dark UI.
      tone = :ink if [:paper, :ink].include?(tone)
      tone = :ochre if tone == :gold
      journal_original_text(bmp, text, x, y, size, tone, align, maximum)
    end
  end
end
