#==============================================================================
# ■ PokemonSummary_Scene — Override visual (estilo Resident Evil)
#------------------------------------------------------------------------------
# Substitui a interface visual do Sumário do Pokémon por um design escuro
# e elegante, no mesmo estilo dos outros plugins RE.
# Sobrescreve apenas os métodos de desenho — lógica de input permanece.
#==============================================================================
# Cursor sized for the RE move rows, above the opaque panel overlay.
class RESummaryMoveSelectionSprite < Sprite
  attr_reader :index, :preselected

  def initialize(viewport = nil, fifthmove = false)
    super(viewport)
    @index = 0
    @preselected = false
    @fifthmove = fifthmove
    self.z = 13
    self.bitmap = Bitmap.new(286, 128)
    [REVisualTheme::GOLD, REVisualTheme::TEXT].each_with_index do |rgb, frame|
      color = Color.new(*rgb)
      top = frame * 64
      self.bitmap.fill_rect(0, top, 286, 1, color)
      self.bitmap.fill_rect(0, top + 63, 286, 1, color)
      self.bitmap.fill_rect(0, top, 3, 64, color)
      self.bitmap.fill_rect(285, top, 1, 64, color)
    end
    refresh
  end

  def index=(value)
    @index = value
    refresh
  end

  def preselected=(value)
    @preselected = value
    refresh
  end

  def refresh
    self.x = 218
    self.y = 92 + (@index * 64)
    self.y -= 76 if @fifthmove
    self.y += 20 if @fifthmove && @index == Pokemon::MAX_MOVES
    self.src_rect.set(0, @preselected ? 64 : 0, 286, 64)
  end

  def dispose
    self.bitmap.dispose if self.bitmap && !self.bitmap.disposed?
    super
  end
end

class PokemonSummary_Scene
  # ── Paleta RE ─────────────────────────────────────────────
  RE_BG_TOP       = REVisualTheme::BG_TOP
  RE_BG_BOTTOM    = REVisualTheme::BG_BOTTOM
  RE_PANEL_BG     = Color.new(*REVisualTheme::PANEL_BG)
  RE_PANEL_BG2    = Color.new(29, 66, 108, 210)
  RE_LINE         = Color.new(*REVisualTheme::GOLD, 210)
  RE_LINE_DIM     = Color.new(*REVisualTheme::GOLD, 65)
  RE_GOLD         = Color.new(*REVisualTheme::GOLD)
  RE_GOLD_DIM     = Color.new(*REVisualTheme::GOLD, 120)

  RE_BASE         = Color.new(*REVisualTheme::TEXT)
  RE_SHADOW       = Color.new(*REVisualTheme::SHADOW)
  RE_TITLE_C      = Color.new(*REVisualTheme::IVORY)
  RE_TITLE_S      = Color.new(*REVisualTheme::SHADOW)
  RE_DIM_C        = Color.new(*REVisualTheme::MUTED)
  RE_DIM_S        = Color.new(*REVisualTheme::SHADOW)
  RE_VAL_C        = Color.new(*REVisualTheme::TEXT)
  RE_VAL_S        = Color.new(*REVisualTheme::SHADOW)
  RE_MALE_C       = Color.new(80, 160, 255)
  RE_FEMALE_C     = Color.new(255, 100, 120)
  RE_SHINY_C      = Color.new(255, 220, 80)

  RE_HP_GREEN     = Color.new(100, 220, 100)
  RE_HP_YELLOW    = Color.new(220, 200, 60)
  RE_HP_RED       = Color.new(220, 80, 60)
  RE_HP_BG        = Color.new(30, 30, 30)
  RE_EXP_C        = Color.new(80, 160, 220)

  RE_STAT_UP      = Color.new(220, 160, 80)
  RE_STAT_DOWN    = Color.new(80, 160, 220)

  RE_PP_OK        = Color.new(200, 200, 200)
  RE_PP_HALF      = Color.new(220, 200, 60)
  RE_PP_LOW       = Color.new(220, 140, 60)
  RE_PP_ZERO      = Color.new(220, 80, 80)

  # ── Abas ──────────────────────────────────────────────────
  PAGE_NAMES = [
    _INTL("INFO"), _INTL("MEMO"), _INTL("STATS"),
    _INTL("MOVES"), _INTL("RIBBONS")
  ]

  # ── Helpers ───────────────────────────────────────────────
  def re_gradient_bg
    REVisualTheme.create_background(Graphics.width, Graphics.height)
  end

  def re_draw_panel(bmp, px, py, pw, ph, color = RE_PANEL_BG)
    REVisualTheme.paint_panel(bmp, px, py, pw, ph, true)
    # Mantem o parametro de cor usado por extensoes, sem apagar a moldura.
    bmp.fill_rect(px + 3, py + 3, pw - 6, ph - 6, color) if color != RE_PANEL_BG
  end

  def re_draw_tabs(bmp, page)
    tab_w = Graphics.width / 5
    5.times do |i|
      tx = i * tab_w
      if (i + 1) == page
        bmp.fill_rect(tx + 1, 1, tab_w - 2, 25, Color.new(*REVisualTheme::GOLD, 38))
        bmp.fill_rect(tx + 4, 2, tab_w - 8, 1, Color.new(*REVisualTheme::GOLD_BRIGHT, 85))
        REVisualTheme.draw_hline(bmp, tx, 26, tab_w)
      else
        bmp.fill_rect(tx, 26, tab_w, 2, RE_LINE_DIM)
      end
      bmp.font.size = 14
      bmp.font.bold = ((i + 1) == page)
      c = (i + 1) == page ? RE_TITLE_C : RE_DIM_C
      s = (i + 1) == page ? RE_TITLE_S : RE_DIM_S
      REPixelUI.draw_text_positions(bmp, [[PAGE_NAMES[i], tx + tab_w / 2, 6, :center, c, s]])
    end
  end

  # ── Override de pbStartScene ──────────────────────────────
  alias re_pbStartScene_orig pbStartScene
  def pbStartScene(party, partyindex, inbattle = false)
    @viewport = Viewport.new(0, 0, Graphics.width, Graphics.height)
    @viewport.z = 99999
    @party      = party
    @partyindex = partyindex
    @pokemon    = @party[@partyindex]
    @inbattle   = inbattle
    @page = 1
    @typebitmap    = AnimatedBitmap.new(_INTL("Graphics/UI/types"))
    @markingbitmap = AnimatedBitmap.new("Graphics/UI/Summary/markings")
    @sprites = {}
    # Fundo gradiente RE (sem imagem)
    @sprites["background"] = Sprite.new(@viewport)
    @sprites["background"].bitmap = re_gradient_bg
    @sprites["background"].z = 0
    # Pokemon sprite
    @sprites["pokemon"] = PokemonSprite.new(@viewport)
    @sprites["pokemon"].setOffset(PictureOrigin::CENTER)
    @sprites["pokemon"].x = 104
    @sprites["pokemon"].y = 180
    @sprites["pokemon"].setPokemonBitmap(@pokemon)
    # Fica acima do painel. Antes, o painel semitransparente era desenhado
    # sobre o sprite e o deixava escuro.
    @sprites["pokemon"].z = 24
    # Pokemon icon
    @sprites["pokeicon"] = PokemonIconSprite.new(@pokemon, @viewport)
    @sprites["pokeicon"].setOffset(PictureOrigin::CENTER)
    @sprites["pokeicon"].x       = 46
    @sprites["pokeicon"].y       = 92
    @sprites["pokeicon"].z       = 24
    @sprites["pokeicon"].visible = false
    # Item icon
    @sprites["itemicon"] = ItemIconSprite.new(30, 320, @pokemon.item_id, @viewport)
    @sprites["itemicon"].blankzero = true
    @sprites["itemicon"].z = 24
    # Overlay para texto
    @sprites["overlay"] = BitmapSprite.new(Graphics.width, Graphics.height, @viewport)
    @sprites["overlay"].z = 12
    pbSetSystemFont(@sprites["overlay"].bitmap)
    # Move selection
    @sprites["movepresel"] = RESummaryMoveSelectionSprite.new(@viewport)
    @sprites["movepresel"].visible     = false
    @sprites["movepresel"].preselected = true
    @sprites["movesel"] = RESummaryMoveSelectionSprite.new(@viewport)
    @sprites["movesel"].visible = false
    # Ribbon selection
    @sprites["ribbonpresel"] = RibbonSelectionSprite.new(@viewport)
    @sprites["ribbonpresel"].visible     = false
    @sprites["ribbonpresel"].preselected = true
    @sprites["ribbonsel"] = RibbonSelectionSprite.new(@viewport)
    @sprites["ribbonsel"].visible = false
    # Arrows
    @sprites["uparrow"] = AnimatedSprite.new("Graphics/UI/up_arrow", 8, 28, 40, 2, @viewport)
    @sprites["uparrow"].x = 350
    @sprites["uparrow"].y = 56
    @sprites["uparrow"].play
    @sprites["uparrow"].visible = false
    @sprites["downarrow"] = AnimatedSprite.new("Graphics/UI/down_arrow", 8, 28, 40, 2, @viewport)
    @sprites["downarrow"].x = 350
    @sprites["downarrow"].y = 260
    @sprites["downarrow"].play
    @sprites["downarrow"].visible = false
    # Marking
    @sprites["markingbg"] = IconSprite.new(260, 88, @viewport)
    @sprites["markingbg"].setBitmap("Graphics/UI/Summary/overlay_marking")
    @sprites["markingbg"].visible = false
    @sprites["markingoverlay"] = BitmapSprite.new(Graphics.width, Graphics.height, @viewport)
    @sprites["markingoverlay"].visible = false
    pbSetSystemFont(@sprites["markingoverlay"].bitmap)
    @sprites["markingsel"] = IconSprite.new(0, 0, @viewport)
    @sprites["markingsel"].setBitmap("Graphics/UI/Summary/cursor_marking")
    @sprites["markingsel"].src_rect.height = @sprites["markingsel"].bitmap.height / 2
    @sprites["markingsel"].visible = false
    # Message box
    @sprites["messagebox"] = Window_AdvancedTextPokemon.new("")
    @sprites["messagebox"].viewport       = @viewport
    @sprites["messagebox"].visible        = false
    @sprites["messagebox"].letterbyletter = true
    pbBottomLeftLines(@sprites["messagebox"], 2)
    # National dex list
    @nationalDexList = [:NONE]
    GameData::Species.each_species { |s| @nationalDexList.push(s.species) }
    drawPage(@page)
    pbFadeInAndShow(@sprites) { pbUpdate }
  end

  # ── Override de drawPage ──────────────────────────────────
  def drawPage(page)
    if @pokemon.egg?
      drawPageOneEgg
      return
    end
    @sprites["pokemon"].setPokemonBitmap(@pokemon)
    @sprites["pokeicon"].pokemon = @pokemon
    @sprites["itemicon"].item = @pokemon.item_id
    overlay = @sprites["overlay"].bitmap
    overlay.clear
    # Fundo (o gradiente já está no sprite "background")
    # Abas de página
    re_draw_tabs(overlay, page)
    # Painel esquerdo (info do pokémon)
    re_draw_panel(overlay, 4, 32, 204, 354)
    # Painel direito (conteúdo da página)
    re_draw_panel(overlay, 212, 32, 296, 354)
    # ── Info do Pokémon (lado esquerdo) ──
    imagepos = []
    # Pokeball
    ballimage = sprintf("Graphics/UI/Summary/icon_ball_%s", @pokemon.poke_ball)
    imagepos.push([ballimage, 14, 60])
    # Status
    status = -1
    if @pokemon.fainted?
      status = GameData::Status.count - 1
    elsif @pokemon.status != :NONE
      status = GameData::Status.get(@pokemon.status).icon_position
    elsif @pokemon.pokerusStage == 1
      status = GameData::Status.count
    end
    if status >= 0
      imagepos.push([_INTL("Graphics/UI/statuses"), 124, 100, 0, 16 * status, 44, 16])
    end
    # Pokérus curado
    if @pokemon.pokerusStage == 2
      imagepos.push(["Graphics/UI/Summary/icon_pokerus", 176, 100])
    end
    # Shiny
    imagepos.push(["Graphics/UI/shiny", 2, 134]) if @pokemon.shiny?
    pbDrawImagePositions(overlay, imagepos)
    # Textos (lado esquerdo)
    textpos = []
    # Nome
    textpos.push([@pokemon.name, 46, 68, :left, RE_BASE, RE_SHADOW])
    # Nível
    textpos.push(["Lv. #{@pokemon.level}", 46, 98, :left, RE_DIM_C, RE_DIM_S])
    # Gênero
    if @pokemon.male?
      textpos.push([_INTL("♂"), 178, 68, :left, RE_MALE_C, Color.new(0, 0, 0, 0)])
    elsif @pokemon.female?
      textpos.push([_INTL("♀"), 178, 68, :left, RE_FEMALE_C, Color.new(0, 0, 0, 0)])
    end
    # Item
    textpos.push([_INTL("Item"), 66, 324, :left, RE_GOLD, RE_TITLE_S])
    if @pokemon.hasItem?
      textpos.push([@pokemon.item.name, 16, 358, :left, RE_VAL_C, RE_VAL_S])
    else
      textpos.push([_INTL("Nenhum"), 16, 358, :left, RE_DIM_C, RE_DIM_S])
    end
    REPixelUI.draw_text_positions(overlay, textpos)
    # Markings
    drawMarkings(overlay, 84, 292)
    # Desenhar página específica
    case page
    when 1 then drawPageOne
    when 2 then drawPageTwo
    when 3 then drawPageThree
    when 4 then drawPageFour
    when 5 then drawPageFive
    end
  end

  # ── Página 1: INFO ────────────────────────────────────────
  def drawPageOne
    overlay = @sprites["overlay"].bitmap
    # Shadow Pokémon heart gauge
    if @pokemon.shadowPokemon?
      shadowfract = @pokemon.heart_gauge.to_f / @pokemon.max_gauge_size
      imagepos = [
        ["Graphics/UI/Summary/overlay_shadow", 224, 240],
        ["Graphics/UI/Summary/overlay_shadowbar", 242, 280, 0, 0, (shadowfract * 248).floor, -1]
      ]
      pbDrawImagePositions(overlay, imagepos)
    end
    # Dex number color
    dexNumBase   = @pokemon.shiny? ? RE_SHINY_C : RE_VAL_C
    dexNumShadow = RE_VAL_S
    textpos = [
      [_INTL("Dex No."), 224, 44, :left, RE_GOLD, RE_TITLE_S],
      [_INTL("Espécie"), 224, 76, :left, RE_GOLD, RE_TITLE_S],
      [@pokemon.speciesName, 440, 76, :center, RE_VAL_C, RE_VAL_S],
      [_INTL("Tipo"), 224, 108, :left, RE_GOLD, RE_TITLE_S],
      [_INTL("OT"), 224, 140, :left, RE_GOLD, RE_TITLE_S],
      [_INTL("ID No."), 224, 172, :left, RE_GOLD, RE_TITLE_S]
    ]
    # Dex number
    dexnum = 0
    dexnumshift = false
    if $player.pokedex.unlocked?(-1)
      dexnum = @nationalDexList.index(@pokemon.species_data.species) || 0
      dexnumshift = true if Settings::DEXES_WITH_OFFSETS.include?(-1)
    else
      ($player.pokedex.dexes_count - 1).times do |i|
        next if !$player.pokedex.unlocked?(i)
        num = pbGetRegionalNumber(i, @pokemon.species)
        break if num <= 0
        dexnum = num
        dexnumshift = true if Settings::DEXES_WITH_OFFSETS.include?(i)
        break
      end
    end
    if dexnum <= 0
      textpos.push(["???", 440, 44, :center, dexNumBase, dexNumShadow])
    else
      dexnum -= 1 if dexnumshift
      textpos.push([sprintf("%03d", dexnum), 440, 44, :center, dexNumBase, dexNumShadow])
    end
    # OT
    if @pokemon.owner.name.empty?
      textpos.push([_INTL("ALUGUEL"), 440, 140, :center, RE_VAL_C, RE_VAL_S])
      textpos.push(["?????", 440, 172, :center, RE_VAL_C, RE_VAL_S])
    else
      ownerbase = RE_VAL_C
      case @pokemon.owner.gender
      when 0 then ownerbase = RE_MALE_C
      when 1 then ownerbase = RE_FEMALE_C
      end
      textpos.push([@pokemon.owner.name, 440, 140, :center, ownerbase, RE_VAL_S])
      textpos.push([sprintf("%05d", @pokemon.owner.public_id), 440, 172, :center, RE_VAL_C, RE_VAL_S])
    end
    # Exp
    if @pokemon.shadowPokemon?
      textpos.push([_INTL("Medidor"), 224, 204, :left, RE_GOLD, RE_TITLE_S])
      heartmessage = [_INTL("O coração está aberto! Desfaça a última tranca!"),
                      _INTL("O coração está quase totalmente aberto."),
                      _INTL("O coração está quase abrindo."),
                      _INTL("O coração está se abrindo mais."),
                      _INTL("O coração está começando a abrir."),
                      _INTL("O coração está trancado.")][@pokemon.heartStage]
      drawTextEx(overlay, 224, 266, 270, 3, heartmessage, RE_VAL_C, RE_VAL_S)
    else
      endexp = @pokemon.growth_rate.minimum_exp_for_level(@pokemon.level + 1)
      textpos.push([_INTL("Exp."), 224, 204, :left, RE_GOLD, RE_TITLE_S])
      textpos.push([@pokemon.exp.to_s_formatted, 494, 236, :right, RE_VAL_C, RE_VAL_S])
      textpos.push([_INTL("Próx. Nv."), 224, 268, :left, RE_GOLD, RE_TITLE_S])
      textpos.push([(endexp - @pokemon.exp).to_s_formatted, 494, 300, :right, RE_VAL_C, RE_VAL_S])
    end
    REPixelUI.draw_text_positions(overlay, textpos)
    # Separadores dourados
    overlay.fill_rect(224, 68, 280, 1, RE_LINE_DIM)
    overlay.fill_rect(224, 100, 280, 1, RE_LINE_DIM)
    overlay.fill_rect(224, 132, 280, 1, RE_LINE_DIM)
    overlay.fill_rect(224, 164, 280, 1, RE_LINE_DIM)
    overlay.fill_rect(224, 196, 280, 1, RE_LINE_DIM)
    overlay.fill_rect(224, 260, 280, 1, RE_LINE_DIM)
    # Types
    @pokemon.types.each_with_index do |type, i|
      type_number = GameData::Type.get(type).icon_position
      type_rect = Rect.new(0, type_number * 28, 64, 28)
      type_x = (@pokemon.types.length == 1) ? 406 : 374 + (66 * i)
      overlay.blt(type_x, 104, @typebitmap.bitmap, type_rect)
    end
    # Exp bar (dourada/azul)
    if @pokemon.level < GameData::GrowthRate.max_level
      bar_x, bar_y, bar_w, bar_h = 224, 330, 280, 8
      overlay.fill_rect(bar_x, bar_y, bar_w, bar_h, RE_HP_BG)
      overlay.fill_rect(bar_x, bar_y, bar_w, 1, RE_LINE_DIM)
      overlay.fill_rect(bar_x, bar_y + bar_h - 1, bar_w, 1, RE_LINE_DIM)
      w = (@pokemon.exp_fraction * bar_w).to_i
      w = ((w / 2).round) * 2
      overlay.fill_rect(bar_x, bar_y + 1, w, bar_h - 2, RE_EXP_C) if w > 0
    end
  end

  # ── Página 1 Egg ──────────────────────────────────────────
  def drawPageOneEgg
    @sprites["itemicon"].item = @pokemon.item_id
    overlay = @sprites["overlay"].bitmap
    overlay.clear
    # Tabs e painéis
    re_draw_tabs(overlay, 1)
    re_draw_panel(overlay, 4, 32, 204, 354)
    re_draw_panel(overlay, 212, 32, 296, 354)
    # Ball
    imagepos = []
    ballimage = sprintf("Graphics/UI/Summary/icon_ball_%s", @pokemon.poke_ball)
    imagepos.push([ballimage, 14, 60])
    pbDrawImagePositions(overlay, imagepos)
    # Textos do ovo
    textpos = [
      [@pokemon.name, 46, 68, :left, RE_BASE, RE_SHADOW],
      [_INTL("Item"), 66, 324, :left, RE_GOLD, RE_TITLE_S]
    ]
    if @pokemon.hasItem?
      textpos.push([@pokemon.item.name, 16, 358, :left, RE_VAL_C, RE_VAL_S])
    else
      textpos.push([_INTL("Nenhum"), 16, 358, :left, RE_DIM_C, RE_DIM_S])
    end
    REPixelUI.draw_text_positions(overlay, textpos)
    # Memo do ovo (lado direito)
    memo = ""
    gold_tag = shadowc3tag(RE_GOLD, RE_TITLE_S)
    val_tag  = shadowc3tag(RE_VAL_C, RE_VAL_S)
    if @pokemon.timeReceived
      date  = @pokemon.timeReceived.day
      month = pbGetMonthName(@pokemon.timeReceived.mon)
      year  = @pokemon.timeReceived.year
      memo += val_tag + _INTL("{1} {2}, {3}", date, month, year) + "\n"
    end
    mapname = pbGetMapNameFromId(@pokemon.obtain_map)
    mapname = @pokemon.obtain_text if @pokemon.obtain_text && !@pokemon.obtain_text.empty?
    if mapname && mapname != ""
      mapname = gold_tag + mapname + val_tag
      memo += val_tag + _INTL("Um misterioso Ovo Pokémon recebido de {1}.", mapname) + "\n"
    else
      memo += val_tag + _INTL("Um misterioso Ovo Pokémon.") + "\n"
    end
    memo += "\n"
    memo += gold_tag + _INTL("\"Observação do Ovo\"") + "\n"
    eggstate = _INTL("Parece que este Ovo vai demorar para chocar.")
    eggstate = _INTL("O que vai sair dele? Não parece perto de chocar.") if @pokemon.steps_to_hatch < 10_200
    eggstate = _INTL("Parece se mover às vezes. Pode estar perto.") if @pokemon.steps_to_hatch < 2550
    eggstate = _INTL("Sons podem ser ouvidos de dentro! Vai chocar logo!") if @pokemon.steps_to_hatch < 1275
    memo += val_tag + eggstate
    drawFormattedTextEx(overlay, 222, 50, 278, memo)
    drawMarkings(overlay, 84, 292)
  end

  # ── Página 2: MEMO ────────────────────────────────────────
  def drawPageTwo
    overlay = @sprites["overlay"].bitmap
    gold_tag = shadowc3tag(RE_GOLD, RE_TITLE_S)
    val_tag  = shadowc3tag(RE_VAL_C, RE_VAL_S)
    memo = ""
    # Nature
    showNature = !@pokemon.shadowPokemon? || @pokemon.heartStage <= 3
    if showNature
      nature_name = gold_tag + @pokemon.nature.name + val_tag
      memo += val_tag + _INTL("Natureza {1}.", nature_name) + "\n"
    end
    # Date received
    if @pokemon.timeReceived
      date  = @pokemon.timeReceived.day
      month = pbGetMonthName(@pokemon.timeReceived.mon)
      year  = @pokemon.timeReceived.year
      memo += val_tag + _INTL("{1} {2}, {3}", date, month, year) + "\n"
    end
    # Map name
    mapname = pbGetMapNameFromId(@pokemon.obtain_map)
    mapname = @pokemon.obtain_text if @pokemon.obtain_text && !@pokemon.obtain_text.empty?
    mapname = _INTL("Lugar distante") if nil_or_empty?(mapname)
    memo += gold_tag + mapname + "\n"
    # Obtain method
    mettext = [
      _INTL("Encontrado no Lv. {1}.", @pokemon.obtain_level),
      _INTL("Ovo recebido."),
      _INTL("Trocado no Lv. {1}.", @pokemon.obtain_level),
      "",
      _INTL("Encontro fatídico no Lv. {1}.", @pokemon.obtain_level)
    ][@pokemon.obtain_method]
    memo += val_tag + mettext + "\n" if mettext && mettext != ""
    # Hatched info
    if @pokemon.obtain_method == 1
      if @pokemon.timeEggHatched
        date  = @pokemon.timeEggHatched.day
        month = pbGetMonthName(@pokemon.timeEggHatched.mon)
        year  = @pokemon.timeEggHatched.year
        memo += val_tag + _INTL("{1} {2}, {3}", date, month, year) + "\n"
      end
      mapname = pbGetMapNameFromId(@pokemon.hatched_map)
      mapname = _INTL("Lugar distante") if nil_or_empty?(mapname)
      memo += gold_tag + mapname + "\n"
      memo += val_tag + _INTL("Ovo chocado.") + "\n"
    else
      memo += "\n"
    end
    # Characteristic
    if showNature
      best_stat = nil
      best_iv = 0
      stats_order = [:HP, :ATTACK, :DEFENSE, :SPEED, :SPECIAL_ATTACK, :SPECIAL_DEFENSE]
      start_point = @pokemon.personalID % stats_order.length
      stats_order.length.times do |i|
        stat = stats_order[(i + start_point) % stats_order.length]
        if !best_stat || @pokemon.iv[stat] > @pokemon.iv[best_stat]
          best_stat = stat
          best_iv = @pokemon.iv[best_stat]
        end
      end
      characteristics = {
        :HP              => [_INTL("Adora comer."),
                             _INTL("Tira muitas sonecas."),
                             _INTL("Cochila bastante."),
                             _INTL("Espalha coisas frequentemente."),
                             _INTL("Gosta de relaxar.")],
        :ATTACK          => [_INTL("Orgulhoso de sua força."),
                             _INTL("Gosta de se agitar."),
                             _INTL("Um pouco temperamental."),
                             _INTL("Gosta de lutar."),
                             _INTL("Temperamento forte.")],
        :DEFENSE         => [_INTL("Corpo resistente."),
                             _INTL("Aguenta bem os golpes."),
                             _INTL("Muito persistente."),
                             _INTL("Boa resistência."),
                             _INTL("Boa perseverança.")],
        :SPECIAL_ATTACK  => [_INTL("Muito curioso."),
                             _INTL("Travesso."),
                             _INTL("Bastante astuto."),
                             _INTL("Frequentemente perdido em pensamentos."),
                             _INTL("Muito exigente.")],
        :SPECIAL_DEFENSE => [_INTL("Determinado."),
                             _INTL("Um tanto vaidoso."),
                             _INTL("Muito desafiador."),
                             _INTL("Odeia perder."),
                             _INTL("Um tanto teimoso.")],
        :SPEED           => [_INTL("Gosta de correr."),
                             _INTL("Alerta a sons."),
                             _INTL("Impetuoso e bobo."),
                             _INTL("Meio palhaço."),
                             _INTL("Foge rapidamente.")]
      }
      memo += val_tag + characteristics[best_stat][best_iv % 5] + "\n"
    end
    drawFormattedTextEx(overlay, 222, 44, 278, memo)
  end

  # ── Página 3: STATS ──────────────────────────────────────
  def drawPageThree
    overlay = @sprites["overlay"].bitmap
    # Nature stat modifiers
    statshadows = {}
    GameData::Stat.each_main { |s| statshadows[s.id] = RE_SHADOW }
    if !@pokemon.shadowPokemon? || @pokemon.heartStage <= 3
      @pokemon.nature_for_stats.stat_changes.each do |change|
        statshadows[change[0]] = Color.new(0, 0, 0, 0) if change[1] > 0
        statshadows[change[0]] = Color.new(0, 0, 0, 0) if change[1] < 0
      end
    end
    stat_colors = {}
    GameData::Stat.each_main { |s| stat_colors[s.id] = RE_BASE }
    if !@pokemon.shadowPokemon? || @pokemon.heartStage <= 3
      @pokemon.nature_for_stats.stat_changes.each do |change|
        stat_colors[change[0]] = RE_STAT_UP if change[1] > 0
        stat_colors[change[0]] = RE_STAT_DOWN if change[1] < 0
      end
    end
    # HP bar
    hp_x, hp_y, hp_w, hp_h = 362, 68, 130, 8
    overlay.fill_rect(hp_x, hp_y, hp_w, hp_h, RE_HP_BG)
    overlay.fill_rect(hp_x, hp_y, hp_w, 1, RE_LINE_DIM)
    overlay.fill_rect(hp_x, hp_y + hp_h - 1, hp_w, 1, RE_LINE_DIM)
    if @pokemon.hp > 0
      w = (@pokemon.hp * hp_w / @pokemon.totalhp.to_f).ceil
      w = [w, 1].max
      hpcolor = RE_HP_GREEN
      hpcolor = RE_HP_YELLOW if @pokemon.hp <= (@pokemon.totalhp / 2).floor
      hpcolor = RE_HP_RED if @pokemon.hp <= (@pokemon.totalhp / 4).floor
      overlay.fill_rect(hp_x, hp_y + 1, w, hp_h - 2, hpcolor)
    end
    # Stats text
    left_x = 224
    val_x  = 494
    textpos = [
      [_INTL("HP"), left_x, 44, :left, stat_colors[:HP], statshadows[:HP]],
      [sprintf("%d / %d", @pokemon.hp, @pokemon.totalhp), val_x, 44, :right, RE_VAL_C, RE_VAL_S],
      [_INTL("Ataque"), left_x, 88, :left, stat_colors[:ATTACK], statshadows[:ATTACK]],
      [@pokemon.attack.to_s, val_x, 88, :right, RE_VAL_C, RE_VAL_S],
      [_INTL("Defesa"), left_x, 120, :left, stat_colors[:DEFENSE], statshadows[:DEFENSE]],
      [@pokemon.defense.to_s, val_x, 120, :right, RE_VAL_C, RE_VAL_S],
      [_INTL("Atq. Esp."), left_x, 152, :left, stat_colors[:SPECIAL_ATTACK], statshadows[:SPECIAL_ATTACK]],
      [@pokemon.spatk.to_s, val_x, 152, :right, RE_VAL_C, RE_VAL_S],
      [_INTL("Def. Esp."), left_x, 184, :left, stat_colors[:SPECIAL_DEFENSE], statshadows[:SPECIAL_DEFENSE]],
      [@pokemon.spdef.to_s, val_x, 184, :right, RE_VAL_C, RE_VAL_S],
      [_INTL("Velocidade"), left_x, 216, :left, stat_colors[:SPEED], statshadows[:SPEED]],
      [@pokemon.speed.to_s, val_x, 216, :right, RE_VAL_C, RE_VAL_S],
      [_INTL("Habilidade"), left_x, 260, :left, RE_GOLD, RE_TITLE_S]
    ]
    # Separadores
    [80, 112, 144, 176, 208, 252].each do |sy|
      overlay.fill_rect(left_x, sy, 280, 1, RE_LINE_DIM)
    end
    # Ability
    ability = @pokemon.ability
    if ability
      textpos.push([ability.name, left_x, 282, :left, RE_VAL_C, RE_VAL_S])
      drawTextEx(overlay, left_x, 310, 280, 2, ability.description, RE_DIM_C, RE_DIM_S)
    end
    REPixelUI.draw_text_positions(overlay, textpos)
  end

  # ── Página 4: MOVES ──────────────────────────────────────
  def drawPageFour
    overlay = @sprites["overlay"].bitmap
    ppBase   = [RE_PP_OK, RE_PP_HALF, RE_PP_LOW, RE_PP_ZERO]
    ppShadow = [RE_VAL_S, RE_VAL_S, RE_VAL_S, RE_VAL_S]
    @sprites["pokemon"].visible  = true
    @sprites["pokeicon"].visible = false
    @sprites["itemicon"].visible = true
    textpos  = []
    imagepos = []
    yPos = 62
    Pokemon::MAX_MOVES.times do |i|
      move = @pokemon.moves[i]
      if move
        type_number = GameData::Type.get(move.display_type(@pokemon)).icon_position
        imagepos.push([_INTL("Graphics/UI/types"), 224, yPos, 0, type_number * 28, 64, 28])
        textpos.push([move.name, 294, yPos + 2, :left, RE_BASE, RE_SHADOW])
        if move.total_pp > 0
          textpos.push([_INTL("PP"), 330, yPos + 30, :left, RE_DIM_C, RE_DIM_S])
          ppfraction = 0
          if move.pp == 0 then ppfraction = 3
          elsif move.pp * 4 <= move.total_pp then ppfraction = 2
          elsif move.pp * 2 <= move.total_pp then ppfraction = 1
          end
          textpos.push([sprintf("%d/%d", move.pp, move.total_pp), 480, yPos + 30, :right,
                        ppBase[ppfraction], ppShadow[ppfraction]])
        end
      else
        textpos.push(["-", 294, yPos + 2, :left, RE_DIM_C, RE_DIM_S])
        textpos.push(["--", 460, yPos + 30, :right, RE_DIM_C, RE_DIM_S])
      end
      # Separador
      overlay.fill_rect(224, yPos + 58, 274, 1, RE_LINE_DIM) if i < Pokemon::MAX_MOVES - 1
      yPos += 64
    end
    REPixelUI.draw_text_positions(overlay, textpos)
    pbDrawImagePositions(overlay, imagepos)
    # The Gen 9 Pack also has move-management options. Keep move details on
    # the usual confirm button and advertise the secondary options shortcut.
    hint = @inbattle ? _INTL("Confirmar: detalhes") :
                       _INTL("Confirmar: detalhes   Ação: opções")
    overlay.font.size = 14
    REPixelUI.draw_text_positions(overlay, [[hint, 361, 350, :center, RE_GOLD, RE_TITLE_S]])
    pbSetSystemFont(overlay)
  end

  # ── Página 4 (selecionando move) ─────────────────────────
  def drawPageFourSelecting(move_to_learn)
    overlay = @sprites["overlay"].bitmap
    overlay.clear
    # Tabs e painéis
    re_draw_tabs(overlay, 4)
    re_draw_panel(overlay, 4, 32, 204, 354)
    re_draw_panel(overlay, 212, 32, 296, 354)
    # Info do pokémon (esquerda)
    textpos = [
      [_INTL("CATEGORIA"), 16, 86, :left, RE_GOLD, RE_TITLE_S],
      [_INTL("PODER"), 16, 118, :left, RE_GOLD, RE_TITLE_S],
      [_INTL("PRECISÃO"), 16, 150, :left, RE_GOLD, RE_TITLE_S]
    ]
    # Types do pokémon
    @pokemon.types.each_with_index do |type, i|
      type_number = GameData::Type.get(type).icon_position
      type_rect = Rect.new(0, type_number * 28, 64, 28)
      # Keep both badges completely inside the left panel. The old dual-type
      # positions ended at x=230 and collided with the move badge at x=224.
      type_x = (@pokemon.types.length == 1) ? 74 : 40 + (70 * i)
      overlay.blt(type_x, 48, @typebitmap.bitmap, type_rect)
    end
    # Moves list (right side)
    ppBase   = [RE_PP_OK, RE_PP_HALF, RE_PP_LOW, RE_PP_ZERO]
    imagepos = []
    # RESummaryMoveSelectionSprite uses y=92 for its first cursor and expects the move
    # contents 8px below it (the Essentials layout convention). Keeping this
    # common origin is especially important for the shifted fifth-move list.
    yPos = 100
    yPos -= 76 if move_to_learn
    limit = move_to_learn ? Pokemon::MAX_MOVES + 1 : Pokemon::MAX_MOVES
    limit.times do |i|
      move = @pokemon.moves[i]
      if i == Pokemon::MAX_MOVES
        move = move_to_learn
        yPos += 20
      end
      if move
        type_number = GameData::Type.get(move.display_type(@pokemon)).icon_position
        imagepos.push([_INTL("Graphics/UI/types"), 224, yPos, 0, type_number * 28, 64, 28])
        textpos.push([move.name, 294, yPos + 2, :left, RE_BASE, RE_SHADOW])
        if move.total_pp > 0
          textpos.push([_INTL("PP"), 330, yPos + 30, :left, RE_DIM_C, RE_DIM_S])
          ppfraction = 0
          if move.pp == 0 then ppfraction = 3
          elsif move.pp * 4 <= move.total_pp then ppfraction = 2
          elsif move.pp * 2 <= move.total_pp then ppfraction = 1
          end
          textpos.push([sprintf("%d/%d", move.pp, move.total_pp), 480, yPos + 30, :right,
                        ppBase[ppfraction], RE_VAL_S])
        end
      else
        textpos.push(["-", 294, yPos + 2, :left, RE_DIM_C, RE_DIM_S])
        textpos.push(["--", 460, yPos + 30, :right, RE_DIM_C, RE_DIM_S])
      end
      yPos += 64
    end
    REPixelUI.draw_text_positions(overlay, textpos)
    pbDrawImagePositions(overlay, imagepos)
  end

  def drawSelectedMove(move_to_learn, selected_move)
    drawPageFourSelecting(move_to_learn)
    overlay = @sprites["overlay"].bitmap
    @sprites["pokemon"].visible = false if @sprites["pokemon"]
    @sprites["pokeicon"].pokemon = @pokemon
    # Nao mostrar o icone durante o aprendizado: ele cobre os textos do painel.
    @sprites["pokeicon"].visible = false
    @sprites["itemicon"].visible = false if @sprites["itemicon"]
    textpos = []
    # Power
    case selected_move.display_damage(@pokemon)
    when 0 then textpos.push(["---", 190, 118, :right, RE_VAL_C, RE_VAL_S])
    when 1 then textpos.push(["???", 190, 118, :right, RE_VAL_C, RE_VAL_S])
    else        textpos.push([selected_move.display_damage(@pokemon).to_s, 190, 118, :right, RE_VAL_C, RE_VAL_S])
    end
    # Accuracy
    if selected_move.display_accuracy(@pokemon) == 0
      textpos.push(["---", 190, 150, :right, RE_VAL_C, RE_VAL_S])
    else
      textpos.push(["#{selected_move.display_accuracy(@pokemon)}%", 190, 150, :right, RE_VAL_C, RE_VAL_S])
    end
    REPixelUI.draw_text_positions(overlay, textpos)
    # Category icon
    imagepos = [["Graphics/UI/category", 140, 82, 0, selected_move.display_category(@pokemon) * 28, 64, 28]]
    pbDrawImagePositions(overlay, imagepos)
    # Description
    drawTextEx(overlay, 10, 182, 196, 5, selected_move.description, RE_DIM_C, RE_DIM_S)
  end

  # ── Página 5: RIBBONS ────────────────────────────────────
  def drawPageFive
    overlay = @sprites["overlay"].bitmap
    @sprites["uparrow"].visible   = false
    @sprites["downarrow"].visible = false
    textpos = [
      [_INTL("Nº de Fitas:"), 224, 338, :left, RE_GOLD, RE_TITLE_S],
      [@pokemon.numRibbons.to_s, 480, 338, :right, RE_VAL_C, RE_VAL_S]
    ]
    REPixelUI.draw_text_positions(overlay, textpos)
    # Show ribbons
    imagepos = []
    coord = 0
    (@ribbonOffset * 4...(@ribbonOffset * 4) + 12).each do |i|
      break if !@pokemon.ribbons[i]
      ribbon_data = GameData::Ribbon.get(@pokemon.ribbons[i])
      ribn = ribbon_data.icon_position
      imagepos.push(["Graphics/UI/Summary/ribbons",
                     230 + (68 * (coord % 4)), 78 + (68 * (coord / 4).floor),
                     64 * (ribn % 8), 64 * (ribn / 8).floor, 64, 64])
      coord += 1
    end
    pbDrawImagePositions(overlay, imagepos)
  end

  def drawSelectedRibbon(ribbonid)
    drawPage(5)
    overlay = @sprites["overlay"].bitmap
    name = ribbonid ? GameData::Ribbon.get(ribbonid).name : ""
    desc = ribbonid ? GameData::Ribbon.get(ribbonid).description : ""
    # Painel de descrição da fita
    re_draw_panel(overlay, 8, 280, 496, 100)
    textpos = [
      [name, 18, 288, :left, RE_GOLD, RE_TITLE_S]
    ]
    REPixelUI.draw_text_positions(overlay, textpos)
    drawTextEx(overlay, 18, 316, 476, 2, desc, RE_VAL_C, RE_VAL_S)
  end

  # ── Override de pbStartForgetScene (theme) ────────────────
  def pbStartForgetScene(party, partyindex, move_to_learn)
    @viewport = Viewport.new(0, 0, Graphics.width, Graphics.height)
    @viewport.z = 99999
    @party      = party
    @partyindex = partyindex
    @pokemon    = @party[@partyindex]
    @page = 4
    @typebitmap = AnimatedBitmap.new(_INTL("Graphics/UI/types"))
    @sprites = {}
    @sprites["background"] = Sprite.new(@viewport)
    @sprites["background"].bitmap = re_gradient_bg
    @sprites["background"].z = 0
    @sprites["overlay"] = BitmapSprite.new(Graphics.width, Graphics.height, @viewport)
    pbSetSystemFont(@sprites["overlay"].bitmap)
    @sprites["pokeicon"] = PokemonIconSprite.new(@pokemon, @viewport)
    @sprites["pokeicon"].setOffset(PictureOrigin::CENTER)
    @sprites["pokeicon"].x       = 46
    @sprites["pokeicon"].y       = 92
    @sprites["pokeicon"].visible = false
    @sprites["movesel"] = RESummaryMoveSelectionSprite.new(@viewport, !move_to_learn.nil?)
    @sprites["movesel"].visible = false
    @sprites["movesel"].visible = true
    @sprites["movesel"].index   = 0
    new_move = (move_to_learn) ? Pokemon::Move.new(move_to_learn) : nil
    drawSelectedMove(new_move, @pokemon.moves[0])
    pbFadeInAndShow(@sprites)
  end
end
