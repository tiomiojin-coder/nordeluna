# One battle-box preference for both sides of the existing battle presentation.
# UI selectors: Toxillian. Emerald graphics: Voltseon / Pokemon Splice Team.
# SwSh-inspired graphics: BiggusWeeabus (adaptation, not the original Switch UI).
# Does not replace battle commands, online synchronization or ability announcements.
module NordelunaDataBoxes
  ROOT = "Plugins/Customizable Battle UI/assets/databoxes"
  STYLES = [
    ["Padrão", "nordeluna"], ["Vermelho", "red"], ["Azul", "blue"],
    ["Emerald", "emerald"], ["SwSh adaptado", "swsh"]
  ].freeze
  REQUIRED = %w[databox_normal databox_normal_foe databox_thin databox_thin_foe overlay_hp overlay_exp icon_numbers]

  def self.valid(value)
    STYLES.any? { |row| row[1] == value } ? value : "nordeluna"
  end

  def self.path(style, name)
    case style
    when "red", "blue"
      # The original CBUI supplies backgrounds; HP/EXP and digits are shared.
      folder = name.start_with?("databox_") ? (style == "red" ? "0/" : "1/") : ""
      "Graphics/UI/Battle/#{folder}#{name}"
    else "#{ROOT}/#{style}/#{name}"
    end
  end

  def self.available?(style)
    style == "nordeluna" || REQUIRED.all? do |name|
      image = path(style, name)
      File.file?(image + ".png") || pbResolveBitmap(image)
    end
  end

  def self.selected(_side)
    return "nordeluna" unless $PokemonSystem
    style = $PokemonSystem.battle_box_style
    available?(style) ? style : "nordeluna"
  end
end

class PokemonSystem
  def battle_box_style
    return NordelunaDataBoxes.valid(@nordeluna_box_style) unless @nordeluna_box_style.nil?
    # Migrate the first independent choice without changing an existing save.
    legacy = [@nordeluna_player_box, @nordeluna_foe_box].find do |value|
      NordelunaDataBoxes.valid(value) == value && value != "nordeluna"
    end
    legacy || "nordeluna"
  end

  def battle_box_style=(value)
    @nordeluna_box_style = NordelunaDataBoxes.valid(value)
    @nordeluna_player_box = @nordeluna_foe_box = @nordeluna_box_style
    # The old red/blue menu theme must not remain a competing box selector.
    self.battle_ui = 0 if @nordeluna_box_style == "red"
    self.battle_ui = 1 if @nordeluna_box_style == "blue"
  end

  # Compatibility with any scripts using the short-lived independent settings.
  def player_box_style; battle_box_style; end
  def foe_box_style; battle_box_style; end
  def player_box_style=(value); self.battle_box_style = value; end
  def foe_box_style=(value); self.battle_box_style = value; end
end

# Replace the ORIGINAL theme entry rather than adding a parallel setting.
# This also removes old entries when scripts are reloaded in a debug session.
MenuHandlers.remove(:options_menu, :player_battle_box)
MenuHandlers.remove(:options_menu, :foe_battle_box)
MenuHandlers.add(:options_menu, :battle_ui, {
  "name" => _INTL("Caixa de batalha"),
  "order" => 105,
  "type" => EnumOption,
  "parameters" => NordelunaDataBoxes::STYLES.map(&:first),
  "description" => _INTL("Muda as caixas dos dois lados na proxima batalha."),
  "get_proc" => proc {
    next NordelunaDataBoxes::STYLES.index { |row| row[1] == $PokemonSystem.battle_box_style } || 0
  },
  "set_proc" => proc { |value, _scene|
    value = 0 unless value.is_a?(Integer) && value.between?(0, NordelunaDataBoxes::STYLES.length - 1)
    $PokemonSystem.battle_box_style = NordelunaDataBoxes::STYLES[value][1]
  }
})

module NordelunaDataBoxes::Renderer
  def initializeDataBoxGraphic(side_size)
    # Resolve once per box; no disk checks in the per-frame update.
    @ndb_style = NordelunaDataBoxes.selected(@battler.index)
    super
    return if @ndb_style == "nordeluna"
    name = side_size == 1 ? "databox_normal" : "databox_thin"
    name += "_foe" if @battler.index.odd?
    @databoxBitmap.dispose
    @databoxBitmap = AnimatedBitmap.new(NordelunaDataBoxes.path(@ndb_style, name))
  end

  def ndb_custom?; @ndb_style && @ndb_style != "nordeluna"; end

  def initializeOtherGraphics(viewport)
    super
    return unless ndb_custom?
    # Preserve the native Sprite/BitmapSprite ownership and animation methods.
    [[:@numbersBitmap, nil, "icon_numbers"], [:@hpBarBitmap, @hpBar, "overlay_hp"],
     [:@expBarBitmap, @expBar, "overlay_exp"]].each do |field, sprite, name|
      sprite.bitmap = nil if sprite
      instance_variable_get(field).dispose
      asset = AnimatedBitmap.new(NordelunaDataBoxes.path(@ndb_style, name))
      instance_variable_set(field, asset)
      sprite.bitmap = asset.bitmap if sprite
    end
    @hpBar.src_rect.height = @hpBarBitmap.height / 3
  end

  def x=(value)
    super
    return unless ndb_custom? && @expBar
    @expBar.x = value + @spriteBaseX + (@ndb_style == "emerald" ? 28 : 6)
  end

  def y=(value)
    super
    return unless ndb_custom? && @expBar
    @expBar.y = value + (@ndb_style == "emerald" ? 78 : 74)
  end

  def ndb_text(label, x, y, width, color = nil)
    font = self.bitmap.font
    previous = [font.size, font.color, font.bold]
    begin
      font.size = 20
      font.bold = false
      dark = ["red", "blue"].include?(@ndb_style)
      font.color = color || (dark ? Color.new(248, 248, 240) : Color.new(64, 64, 64))
      font.size -= 1 while font.size > 12 && self.bitmap.text_size(label).width > width
      self.bitmap.draw_text(x, y, width, 24, label)
    ensure
      font.size, font.color, font.bold = previous
    end
  end

  def draw_background
    return super unless ndb_custom?
    self.bitmap.blt(0, 0, @databoxBitmap.bitmap, Rect.new(0, 0, @databoxBitmap.width, @databoxBitmap.height))
  end

  def draw_name
    return super unless ndb_custom?
    ndb_text(@battler.name, @spriteBaseX + 8, 10, 116)
  end

  def draw_level
    return super unless ndb_custom?
    ndb_text("Lv.#{@battler.level}", @spriteBaseX + 145, 10, 60)
  end

  def draw_gender
    return super unless ndb_custom?
    gender = @battler.displayGender
    return unless [0, 1].include?(gender)
    dark = ["red", "blue"].include?(@ndb_style)
    male = dark ? Color.new(96, 208, 255) : Color.new(48, 96, 216)
    female = dark ? Color.new(255, 200, 220) : Color.new(216, 72, 72)
    ndb_text(gender == 0 ? "♂" : "♀", @spriteBaseX + 126, 10, 18, gender == 0 ? male : female)
  end

  def draw_status
    return super unless ndb_custom?
    return if @battler.status == :NONE
    position = if @battler.status == :POISON && @battler.statusCount > 0
                 GameData::Status.count - 1
               else
                 GameData::Status.get(@battler.status).icon_position
               end
    return if position < 0
    pbDrawImagePositions(self.bitmap, [["Graphics/UI/Battle/icon_statuses", @spriteBaseX + 24, 36,
                                      0, position * 16, -1, 16]])
  end

  def draw_shiny_icon
    return super unless ndb_custom?
    return unless @battler.shiny?
    offset = @battler.opposes?(0) ? 206 : -6
    pbDrawImagePositions(self.bitmap, [["Graphics/UI/shiny", @spriteBaseX + offset, 36]])
  end

  def draw_owned_icon
    return super unless ndb_custom?
    return unless @battler.owned? && @battler.opposes?(0)
    pbDrawImagePositions(self.bitmap, [["Graphics/UI/Battle/icon_own", @spriteBaseX + 8, 36]])
  end

  def draw_special_form_icon
    return super unless ndb_custom?
    path = if @battler.mega?
             "Graphics/UI/Battle/icon_mega"
           elsif @battler.primal? && @battler.isSpecies?(:GROUDON)
             "Graphics/UI/Battle/icon_primal_Groudon"
           elsif @battler.primal? && @battler.isSpecies?(:KYOGRE)
             "Graphics/UI/Battle/icon_primal_Kyogre"
           end
    pbDrawImagePositions(self.bitmap, [[path, @spriteBaseX + 8, 34]]) if path
  end

  def pbDrawNumber(number, bitmap, x, y, align = :left)
    return super unless ndb_custom?
    digits = number == -1 ? [10] : number.to_i.digits.reverse
    width = @numbersBitmap.width / 11
    x -= width * digits.length if align == :right
    digits.each do |digit|
      bitmap.blt(x, y, @numbersBitmap.bitmap, Rect.new(digit * width, 0, width, @numbersBitmap.height))
      x += width
    end
  end
end

Battle::Scene::PokemonDataBox.prepend(NordelunaDataBoxes::Renderer)
