#==============================================================================
# ■ PokemonPokedex_Scene — Override completo (estilo Resident Evil)
#------------------------------------------------------------------------------
# Substitui a interface visual da Pokédex por um design escuro e elegante
# inspirado em Resident Evil. Usa o mesmo estilo visual do RE Menu e RE Bag.
#
# O controller (PokemonPokedexScreen) permanece inalterado — só a aparência
# muda. Mantém compatibilidade total com as sub-telas de entrada e busca.
#==============================================================================

# Constantes de modo (compatibilidade com o engine)
MODENUMERICAL    = 0 unless defined?(MODENUMERICAL)
MODEALPHABETICAL = 1 unless defined?(MODEALPHABETICAL)

class PokemonPokedex_Scene
  #==========================================================================
  # ● CONFIGURAÇÃO VISUAL
  #==========================================================================
  RE_BG_TOP       = REVisualTheme::BG_TOP
  RE_BG_BOTTOM    = REVisualTheme::BG_BOTTOM
  RE_PANEL_BG     = REVisualTheme::PANEL_BG
  RE_LINE_COLOR   = REVisualTheme::LINE_COLOR

  RE_TITLE_COLOR  = REVisualTheme::IVORY
  RE_TITLE_SHADOW = REVisualTheme::SHADOW

  RE_ITEM_COLOR   = REVisualTheme::TEXT
  RE_ITEM_SHADOW  = REVisualTheme::SHADOW

  RE_SEL_COLOR    = REVisualTheme::GOLD_BRIGHT
  RE_SEL_SHADOW   = REVisualTheme::SHADOW

  RE_DIM_COLOR    = REVisualTheme::MUTED
  RE_DIM_SHADOW   = [30, 30, 30]

  RE_OWNED_COLOR  = [180, 220, 160]
  RE_OWNED_SHADOW = [50, 80, 30]

  RE_DESC_COLOR   = REVisualTheme::MUTED
  RE_DESC_SHADOW  = REVisualTheme::SHADOW

  RE_NUM_COLOR    = [160, 150, 120]
  RE_NUM_SHADOW   = [40, 40, 30]

  RE_CURSOR_COLOR  = [200, 180, 100, 50]
  RE_CURSOR_BORDER = [200, 180, 100, 160]

  RE_TITLE_FONT  = 26
  RE_ITEM_FONT   = 20
  RE_NUM_FONT    = 18
  RE_INFO_FONT   = 18
  RE_SMALL_FONT  = 16

  RE_ITEMS_VISIBLE = 9
  RE_ITEM_HEIGHT   = 32
  RE_LIST_TOP      = 60
  RE_LIST_WIDTH    = 280
  RE_TEXT_LEFT     = 16

  RE_INFO_X      = 296
  RE_INFO_WIDTH  = 212

  RE_PULSE_MIN   = REVisualTheme::CURSOR_MIN
  RE_PULSE_MAX   = REVisualTheme::CURSOR_MAX
  RE_PULSE_SPEED = 3

  #==========================================================================
  # ● INTERFACE PÚBLICA
  #==========================================================================

  def pbStartScene
    @sprites = {}
    @viewport = Viewport.new(0, 0, Graphics.width, Graphics.height)
    @viewport.z = 99999
    @disposed = false
    @pulse_frame = 0
    @index = 0
    @scroll = 0
    @searchResults = false
    @searchParams = [MODENUMERICAL, -1, -1, -1, -1, -1, -1, -1, -1, -1]
    # Construir lista do Pokédex
    build_dex_list
    # Restaurar posição salva
    saved_idx = $PokemonGlobal.pokedexIndex[pbGetSavePositionIndex] rescue 0
    @index = [[saved_idx.to_i, 0].max, [@dexlist.length - 1, 0].max].min
    adjust_scroll
    # Criar elementos visuais
    create_background
    create_title
    create_list_panel
    create_cursor
    create_items_sprite
    create_info_panel
    create_pokemon_sprite
    # Desenhar
    draw_items
    draw_info
    update_cursor_y
    # Animação de entrada
    animate_fade_in
  end

  def pbEndScene
    animate_fade_out
    dispose_all
  end

  def pbPokedex
    loop do
      Graphics.update
      Input.update
      update_pulse
      # Navegação
      if Input.trigger?(Input::UP) || Input.repeat?(Input::UP)
        move_cursor(-1)
      elsif Input.trigger?(Input::DOWN) || Input.repeat?(Input::DOWN)
        move_cursor(1)
      elsif Input.trigger?(Input::LEFT)
        move_cursor(-RE_ITEMS_VISIBLE)
      elsif Input.trigger?(Input::RIGHT)
        move_cursor(RE_ITEMS_VISIBLE)
      end
      # Confirmar — ver entrada
      if Input.trigger?(Input::USE)
        if @dexlist.length > 0 && @dexlist[@index]
          species = @dexlist[@index][:species]
          if $player.pokedex.seen?(species)
            pbPlayDecisionSE
            pbDexEntry(@index)
          else
            pbPlayBuzzerSE
          end
        end
      end
      # Busca
      if Input.trigger?(Input::ACTION)
        pbPlayDecisionSE
        pbDexSearch
      end
      # Voltar
      if Input.trigger?(Input::BACK)
        pbPlayCloseMenuSE
        if @searchResults
          close_search
        else
          break
        end
      end
    end
  end

  #==========================================================================
  # ● CONSTRUÇÃO DA DEX LIST
  #==========================================================================

  private

  def pbGetSavePositionIndex
    region = pbGetPokedexRegion
    return region if region >= 0
    dex_names = Settings.pokedex_names rescue []
    return dex_names.length
  end

  def build_dex_list
    @dexlist = []
    region = pbGetPokedexRegion
    GameData::Species.each do |sp|
      next if sp.form != 0
      if region >= 0
        num = pbGetRegionalNumber(region, sp.id)
        next if num <= 0
      else
        num = sp.id_number
      end
      @dexlist.push({
        species: sp.id,
        name:    sp.real_name,
        number:  num
      })
    end
    @dexlist.sort_by! { |e| e[:number] }
    # Modo alfabético
    mode = $PokemonGlobal.pokedexMode rescue MODENUMERICAL
    if mode == MODEALPHABETICAL
      @dexlist.sort_by! { |e| e[:name] }
    end
  end

  #==========================================================================
  # ● ENTRADA E BUSCA
  #==========================================================================

  def pbDexEntry(index)
    # Fade out elementos
    hide_sprites
    # Abrir tela de info
    region = -1
    if !Settings::USE_CURRENT_REGION_DEX
      dex_names = Settings.pokedex_names rescue []
      si = pbGetSavePositionIndex
      if dex_names[si].is_a?(Array)
        region = dex_names[si][1]
      end
    end
    scene  = PokemonPokedexInfo_Scene.new
    screen = PokemonPokedexInfoScreen.new(scene)
    ret = screen.pbStartScreen(@dexlist, index, region)
    # Se estava em busca, re-filtrar
    if @searchResults
      new_list = pbSearchDexList(@searchParams)
      @dexlist = new_list
      ret = [@dexlist.length - 1, 0].max if ret >= @dexlist.length
      ret = 0 if ret < 0
    else
      build_dex_list
      $PokemonGlobal.pokedexIndex[pbGetSavePositionIndex] = ret
    end
    @index = [[ret, 0].max, [@dexlist.length - 1, 0].max].min
    @scroll = 0
    adjust_scroll
    show_sprites
    draw_items
    draw_info
    update_cursor_y
  end

  def pbDexSearch
    # Menu de busca simplificado no estilo RE
    hide_sprites
    result = show_search_menu
    if result
      @searchResults = true
      @dexlist = result
      @index = 0
      @scroll = 0
      adjust_scroll
    end
    show_sprites
    draw_items
    draw_info
    update_cursor_y
  end

  def close_search
    @searchResults = false
    $PokemonGlobal.pokedexMode = MODENUMERICAL
    @searchParams = [MODENUMERICAL, -1, -1, -1, -1, -1, -1, -1, -1, -1]
    build_dex_list
    saved_idx = $PokemonGlobal.pokedexIndex[pbGetSavePositionIndex] rescue 0
    @index = [[saved_idx.to_i, 0].max, [@dexlist.length - 1, 0].max].min
    @scroll = 0
    adjust_scroll
    draw_items
    draw_info
    update_cursor_y
  end

  #--------------------------------------------------------------------------
  # Menu de busca simplificado (estilo RE)
  #--------------------------------------------------------------------------
  def show_search_menu
    search_vp = Viewport.new(0, 0, Graphics.width, Graphics.height)
    search_vp.z = 100010

    # Fundo
    bg = Sprite.new(search_vp)
    bg.bitmap = create_gradient_bg
    bg.z = 0

    # Título
    title_spr = Sprite.new(search_vp)
    title_spr.bitmap = Bitmap.new(Graphics.width, 50)
    title_spr.z = 10
    REVisualTheme.draw_header_band(title_spr.bitmap, 8, 3,
                                   Graphics.width - 16, 45)
    pbSetSystemFont(title_spr.bitmap)
    title_spr.bitmap.font.size = RE_TITLE_FONT
    tc = Color.new(*RE_TITLE_COLOR)
    ts = Color.new(*RE_TITLE_SHADOW)
    REPixelUI.draw_text_positions(title_spr.bitmap, [
      [_INTL("BUSCA"), RE_TEXT_LEFT, 12, 0, tc, ts]
    ])
    REVisualTheme.draw_hline(title_spr.bitmap, RE_TEXT_LEFT - 4, 44, 260)

    # Opções de busca
    options = [
      _INTL("Ordem: Numérica"),
      _INTL("Ordem: Alfabética"),
      _INTL("Apenas Vistos"),
      _INTL("Apenas Capturados"),
      _INTL("Cancelar")
    ]
    opt_spr = Sprite.new(search_vp)
    opt_spr.bitmap = Bitmap.new(Graphics.width, Graphics.height)
    opt_spr.z = 10

    # Cursor
    cur_spr = Sprite.new(search_vp)
    cur_w = 260
    cur_h = 30
    cur_bmp = REVisualTheme.create_cursor(cur_w, cur_h)
    cur_spr.bitmap = cur_bmp
    cur_spr.z = 8

    si = 0

    # Desenhar opções
    draw_search_options = proc {
      opt_spr.bitmap.clear
      REVisualTheme.paint_panel(opt_spr.bitmap, RE_TEXT_LEFT - 4, 54,
                                276, options.length * 36 + 14, true)
      pbSetSystemFont(opt_spr.bitmap)
      opt_spr.bitmap.font.size = RE_ITEM_FONT
      options.each_with_index do |opt, i|
        y = 60 + i * 36
        if i == si
          nc = Color.new(*RE_SEL_COLOR)
          ns = Color.new(*RE_SEL_SHADOW)
        else
          nc = Color.new(*RE_ITEM_COLOR)
          ns = Color.new(*RE_ITEM_SHADOW)
        end
        REPixelUI.draw_text_positions(opt_spr.bitmap, [
          [opt, RE_TEXT_LEFT + 12, y + 4, 0, nc, ns]
        ])
      end
      cur_spr.x = RE_TEXT_LEFT
      cur_spr.y = 60 + si * 36
    }
    draw_search_options.call

    result = nil
    loop do
      Graphics.update
      Input.update
      if Input.trigger?(Input::UP)
        si = (si - 1) % options.length
        pbPlayCursorSE
        draw_search_options.call
      elsif Input.trigger?(Input::DOWN)
        si = (si + 1) % options.length
        pbPlayCursorSE
        draw_search_options.call
      elsif Input.trigger?(Input::USE)
        pbPlayDecisionSE
        case si
        when 0  # Numérica
          $PokemonGlobal.pokedexMode = MODENUMERICAL
          build_dex_list
          result = @dexlist
        when 1  # Alfabética
          $PokemonGlobal.pokedexMode = MODEALPHABETICAL
          build_dex_list
          result = @dexlist
        when 2  # Apenas Vistos
          filtered = @dexlist.select { |e| $player.pokedex.seen?(e[:species]) }
          result = filtered if filtered.length > 0
        when 3  # Apenas Capturados
          filtered = @dexlist.select { |e| $player.pokedex.owned?(e[:species]) }
          result = filtered if filtered.length > 0
        when 4  # Cancelar
          result = nil
        end
        break
      elsif Input.trigger?(Input::BACK)
        pbPlayCancelSE
        break
      end
    end

    # Limpar
    bg.bitmap.dispose; bg.dispose
    title_spr.bitmap.dispose; title_spr.dispose
    opt_spr.bitmap.dispose; opt_spr.dispose
    cur_spr.bitmap.dispose; cur_spr.dispose
    search_vp.dispose
    result
  end

  def pbSearchDexList(params)
    # Compatibilidade com sistema de busca padrão
    build_dex_list
    @dexlist
  end

  #==========================================================================
  # ● CRIAÇÃO DOS SPRITES
  #==========================================================================

  def create_gradient_bg
    REVisualTheme.create_background(Graphics.width, Graphics.height)
  end

  def create_background
    @sprites["bg"] = Sprite.new(@viewport)
    @sprites["bg"].bitmap = create_gradient_bg
    @sprites["bg"].z = 0
  end

  def create_title
    @sprites["title"] = Sprite.new(@viewport)
    @sprites["title"].bitmap = Bitmap.new(Graphics.width, 52)
    @sprites["title"].z = 20
    bmp = @sprites["title"].bitmap
    REVisualTheme.draw_header_band(bmp, 8, 3, Graphics.width - 16, 47)
    pbSetSystemFont(bmp)
    bmp.font.size = RE_TITLE_FONT
    tc = Color.new(*RE_TITLE_COLOR)
    ts = Color.new(*RE_TITLE_SHADOW)
    label = @searchResults ? _INTL("POKÉDEX — Busca") : _INTL("POKÉDEX")
    REPixelUI.draw_text_positions(bmp, [
      [label, RE_TEXT_LEFT, 10, 0, tc, ts]
    ])
    # Linha abaixo do título
    REVisualTheme.draw_hline(bmp, RE_TEXT_LEFT - 4, 44, RE_LIST_WIDTH - 10)
    # Contagem
    seen = 0; owned = 0
    @dexlist.each do |e|
      seen += 1 if $player.pokedex.seen?(e[:species])
      owned += 1 if $player.pokedex.owned?(e[:species])
    end
    bmp.font.size = RE_SMALL_FONT
    dc = Color.new(*RE_DESC_COLOR)
    ds = Color.new(*RE_DESC_SHADOW)
    count_text = _INTL("Vistos: {1}  Capturados: {2}", seen, owned)
    REPixelUI.draw_text_positions(bmp, [
      [count_text, Graphics.width - 12, 14, 1, dc, ds]
    ])
  end

  def create_list_panel
    @sprites["list_bg"] = Sprite.new(@viewport)
    w = RE_LIST_WIDTH
    h = RE_ITEMS_VISIBLE * RE_ITEM_HEIGHT + 8
    bmp = REVisualTheme.create_panel(w, h, true)
    @sprites["list_bg"].bitmap = bmp
    @sprites["list_bg"].x = 4
    @sprites["list_bg"].y = RE_LIST_TOP
    @sprites["list_bg"].z = 5
  end

  def create_cursor
    @sprites["cursor"] = Sprite.new(@viewport)
    w = RE_LIST_WIDTH - 12
    h = RE_ITEM_HEIGHT
    bmp = REVisualTheme.create_cursor(w, h)
    @sprites["cursor"].bitmap = bmp
    @sprites["cursor"].z = 12
  end

  def create_items_sprite
    @sprites["items"] = Sprite.new(@viewport)
    w = RE_LIST_WIDTH
    h = RE_ITEMS_VISIBLE * RE_ITEM_HEIGHT + 8
    @sprites["items"].bitmap = Bitmap.new(w, h)
    @sprites["items"].x = 4
    @sprites["items"].y = RE_LIST_TOP
    @sprites["items"].z = 18
  end

  def create_info_panel
    # Painel de informações à direita
    @sprites["info_bg"] = Sprite.new(@viewport)
    pw = RE_INFO_WIDTH
    ph = Graphics.height - RE_LIST_TOP - 8
    bmp = REVisualTheme.create_panel(pw, ph, true)
    @sprites["info_bg"].bitmap = bmp
    @sprites["info_bg"].x = RE_INFO_X
    @sprites["info_bg"].y = RE_LIST_TOP
    @sprites["info_bg"].z = 5

    @sprites["info_text"] = Sprite.new(@viewport)
    @sprites["info_text"].bitmap = Bitmap.new(pw - 16, ph - 16)
    @sprites["info_text"].x = RE_INFO_X + 8
    @sprites["info_text"].y = RE_LIST_TOP + 8
    @sprites["info_text"].z = 20
  end

  def create_pokemon_sprite
    @sprites["pkmn_icon"] = Sprite.new(@viewport)
    @sprites["pkmn_icon"].z = 22
  end

  #==========================================================================
  # ● RENDERIZAÇÃO
  #==========================================================================

  def draw_items
    bmp = @sprites["items"].bitmap
    bmp.clear
    pbSetSystemFont(bmp)
    return if @dexlist.empty?

    total = @dexlist.length
    RE_ITEMS_VISIBLE.times do |vi|
      real_i = @scroll + vi
      break if real_i >= total
      entry = @dexlist[real_i]
      y = vi * RE_ITEM_HEIGHT + 4
      is_sel = (real_i == @index)

      species = entry[:species]
      seen  = $player.pokedex.seen?(species)
      owned = $player.pokedex.owned?(species)

      # Número
      bmp.font.size = RE_NUM_FONT
      num_text = format("%03d", entry[:number])
      nc = Color.new(*RE_NUM_COLOR)
      ns = Color.new(*RE_NUM_SHADOW)
      REPixelUI.draw_text_positions(bmp, [
        [num_text, RE_TEXT_LEFT, y + 6, 0, nc, ns]
      ])

      # Nome ou ???
      bmp.font.size = RE_ITEM_FONT
      if seen
        name = entry[:name]
        if is_sel
          color  = Color.new(*RE_SEL_COLOR)
          shadow = Color.new(*RE_SEL_SHADOW)
        elsif owned
          color  = Color.new(*RE_OWNED_COLOR)
          shadow = Color.new(*RE_OWNED_SHADOW)
        else
          color  = Color.new(*RE_ITEM_COLOR)
          shadow = Color.new(*RE_ITEM_SHADOW)
        end
      else
        name = "———"
        if is_sel
          color  = Color.new(*RE_DIM_COLOR)
          shadow = Color.new(*RE_DIM_SHADOW)
        else
          color  = Color.new(70, 70, 70)
          shadow = Color.new(20, 20, 20)
        end
      end
      REPixelUI.draw_text_positions(bmp, [
        [name, RE_TEXT_LEFT + 50, y + 4, 0, color, shadow]
      ])

      # Indicadores de estado (visto / capturado)
      if owned
        ic = Color.new(180, 220, 160, 200)
        # Pokéball indicator
        bmp.font.size = RE_SMALL_FONT
        REPixelUI.draw_text_positions(bmp, [
          ["●", RE_LIST_WIDTH - 28, y + 6, 1, ic, Color.new(0, 0, 0, 0)]
        ])
      elsif seen
        ic = Color.new(200, 180, 100, 150)
        bmp.font.size = RE_SMALL_FONT
        REPixelUI.draw_text_positions(bmp, [
          ["○", RE_LIST_WIDTH - 28, y + 6, 1, ic, Color.new(0, 0, 0, 0)]
        ])
      end

      # Divisor
      if vi < RE_ITEMS_VISIBLE - 1 && real_i < total - 1
        dc = Color.new(RE_LINE_COLOR[0], RE_LINE_COLOR[1], RE_LINE_COLOR[2], 30)
        bmp.fill_rect(RE_TEXT_LEFT, y + RE_ITEM_HEIGHT - 1,
                       RE_LIST_WIDTH - RE_TEXT_LEFT * 2, 1, dc)
      end
    end

    # Indicadores de scroll
    lc = Color.new(*RE_LINE_COLOR)
    cx = RE_LIST_WIDTH / 2
    if @scroll > 0
      bmp.fill_rect(cx - 8, 0, 16, 2, lc)
    end
    if @scroll + RE_ITEMS_VISIBLE < total
      bottom = RE_ITEMS_VISIBLE * RE_ITEM_HEIGHT + 4
      bmp.fill_rect(cx - 8, bottom, 16, 2, lc)
    end
  end

  def draw_info
    bmp = @sprites["info_text"].bitmap
    bmp.clear
    # Limpar sprite do Pokémon
    if @sprites["pkmn_icon"].bitmap && !@sprites["pkmn_icon"].bitmap.disposed?
      @sprites["pkmn_icon"].bitmap.dispose
    end
    @sprites["pkmn_icon"].bitmap = nil

    return if @dexlist.empty? || @index >= @dexlist.length
    entry = @dexlist[@index]
    species = entry[:species]
    seen  = $player.pokedex.seen?(species)
    owned = $player.pokedex.owned?(species)

    pbSetSystemFont(bmp)

    # Número grande
    bmp.font.size = RE_TITLE_FONT
    tc = Color.new(*RE_TITLE_COLOR)
    ts = Color.new(*RE_TITLE_SHADOW)
    REPixelUI.draw_text_positions(bmp, [
      [format("N° %03d", entry[:number]), 4, 0, 0, tc, ts]
    ])

    # Nome e dados lado a lado no cabecalho. Nenhum texto ocupa o retrato.
    name_width = owned ? 92 : bmp.width - 8
    bmp.font.size = RE_ITEM_FONT
    if seen
      nc = owned ? Color.new(*RE_OWNED_COLOR) : Color.new(*RE_ITEM_COLOR)
      ns = owned ? Color.new(*RE_OWNED_SHADOW) : Color.new(*RE_ITEM_SHADOW)
      REPixelUI.draw_text_positions(bmp, [
        [info_fit_text(bmp, entry[:name], name_width), 4, 30, 0, nc, ns]
      ])
    else
      dc = Color.new(*RE_DIM_COLOR)
      ds = Color.new(*RE_DIM_SHADOW)
      REPixelUI.draw_text_positions(bmp, [
        ["???", 4, 30, 0, dc, ds]
      ])
    end

    # Info adicional (se capturado)
    header_height = owned ? 100 : 82
    if owned
      sp_data = GameData::Species.get(species)
      info_x = 104
      info_y = 4
      info_width = bmp.width - info_x - 2
      bmp.font.size = 14
      dc = Color.new(*RE_DESC_COLOR)
      ds = Color.new(*RE_DESC_SHADOW)
      # Tipos em linhas separadas acomodam nomes longos sem invadir o nome.
      details = sp_data.types.map { |t| GameData::Type.get(t).name }
      details << sp_data.category if sp_data.respond_to?(:category)
      details << _INTL("Alt.: {1} m", format("%.1f", sp_data.height.to_f / 10))
      details << _INTL("Peso: {1} kg", format("%.1f", sp_data.weight.to_f / 10))
      details.each do |detail|
        REPixelUI.draw_text_positions(bmp, [
          [info_fit_text(bmp, detail, info_width), info_x, info_y, 0, dc, ds]
        ])
        info_y += 18
      end
      header_height = [header_height, info_y + 6].max
      bmp.fill_rect(98, 4, 1, header_height - 12, Color.new(*RE_LINE_COLOR))
    elsif seen
      bmp.font.size = RE_SMALL_FONT
      dc = Color.new(*RE_DIM_COLOR)
      ds = Color.new(*RE_DIM_SHADOW)
      REPixelUI.draw_text_positions(bmp, [
        [_INTL("Capture para mais dados."), 4, 58, 0, dc, ds]
      ])
    end

    bmp.fill_rect(0, header_height, bmp.width, 2, Color.new(*RE_LINE_COLOR))

    # Retrato contido entre o cabecalho e o estado; sprites grandes tambem cabem.
    if seen
      icon_path = GameData::Species.front_sprite_filename(species)
      if icon_path && pbResolveBitmap(icon_path)
        icon = @sprites["pkmn_icon"]
        icon.bitmap = Bitmap.new(icon_path)
        area_y = header_height + 10
        area_h = [bmp.height - 32 - area_y, 1].max
        # Preserve the original sprite pixels; fractional zoom blurs pixel art.
        scale = 1.0
        icon.zoom_x = icon.zoom_y = scale
        icon.x = @sprites["info_text"].x + (bmp.width - icon.bitmap.width * scale) / 2
        icon.y = @sprites["info_text"].y + area_y + (area_h - icon.bitmap.height * scale) / 2
      end
    end

    # Estado
    bmp.font.size = RE_SMALL_FONT
    state_y = bmp.height - 24
    if owned
      sc = Color.new(*RE_OWNED_COLOR)
      ss = Color.new(*RE_OWNED_SHADOW)
      REPixelUI.draw_text_positions(bmp, [
        [_INTL("● Capturado"), 4, state_y, 0, sc, ss]
      ])
    elsif seen
      sc = Color.new(*RE_NUM_COLOR)
      ss = Color.new(*RE_NUM_SHADOW)
      REPixelUI.draw_text_positions(bmp, [
        [_INTL("○ Visto"), 4, state_y, 0, sc, ss]
      ])
    end
  end

  # Ajusta cada rotulo ao seu proprio campo, sem cobrir a coluna vizinha.
  def info_fit_text(bmp, text, width)
    value = text.to_s.dup
    return value if bmp.text_size(value).width <= width
    value = value[0...-1] while !value.empty? && bmp.text_size(value + "...").width > width
    value + "..."
  end

  #==========================================================================
  # ● NAVEGAÇÃO
  #==========================================================================

  def move_cursor(dir)
    return if @dexlist.empty?
    old = @index
    total = @dexlist.length
    @index = (@index + dir) % total
    @index = total - 1 if @index < 0
    if @index != old
      pbPlayCursorSE
      adjust_scroll
      update_cursor_y
      draw_items
      draw_info
      # Salvar posição
      unless @searchResults
        $PokemonGlobal.pokedexIndex[pbGetSavePositionIndex] = @index
      end
    end
  end

  def update_cursor_y
    vi = @index - @scroll
    @sprites["cursor"].x = 10
    @sprites["cursor"].y = RE_LIST_TOP + vi * RE_ITEM_HEIGHT + 4
  end

  def adjust_scroll
    return if @dexlist.empty?
    total = @dexlist.length
    if @index < @scroll
      @scroll = @index
    elsif @index >= @scroll + RE_ITEMS_VISIBLE
      @scroll = @index - RE_ITEMS_VISIBLE + 1
    end
    @scroll = [[0, @scroll].max, [total - RE_ITEMS_VISIBLE, 0].max].min
  end

  #==========================================================================
  # ● ANIMAÇÕES E UTILITIES
  #==========================================================================

  def update_pulse
    @pulse_frame += 1
    range = RE_PULSE_MAX - RE_PULSE_MIN
    wave = Math.sin(@pulse_frame.to_f * RE_PULSE_SPEED / 60.0 * Math::PI)
    @sprites["cursor"].opacity = (RE_PULSE_MIN + range * (wave + 1) / 2.0).to_i
  end

  def animate_fade_in
    overlay = Sprite.new(@viewport)
    overlay.bitmap = Bitmap.new(Graphics.width, Graphics.height)
    overlay.bitmap.fill_rect(0, 0, Graphics.width, Graphics.height, Color.new(0, 0, 0))
    overlay.z = 9999
    overlay.opacity = 255
    slide_keys = ["title", "list_bg", "items", "cursor", "info_bg", "info_text", "pkmn_icon"]
    originals = {}
    slide_keys.each do |key|
      next unless @sprites[key] && !@sprites[key].disposed?
      originals[key] = @sprites[key].x
    end
    offset = -60
    frames = 14
    frames.times do |i|
      t = (i + 1).to_f / frames
      f = 1.0 - (1.0 - t) ** 2
      overlay.opacity = (255 * (1.0 - f)).to_i
      slide = (offset * (1.0 - f)).to_i
      slide_keys.each do |key|
        next unless originals[key]
        @sprites[key].x = originals[key] + slide
      end
      Graphics.update
      Input.update
    end
    slide_keys.each do |key|
      next unless originals[key]
      @sprites[key].x = originals[key]
    end
    overlay.opacity = 0
    overlay.bitmap.dispose
    overlay.dispose
  end

  def animate_fade_out
    overlay = Sprite.new(@viewport)
    overlay.bitmap = Bitmap.new(Graphics.width, Graphics.height)
    overlay.bitmap.fill_rect(0, 0, Graphics.width, Graphics.height, Color.new(0, 0, 0))
    overlay.z = 9999
    overlay.opacity = 0
    slide_keys = ["title", "list_bg", "items", "cursor", "info_bg", "info_text", "pkmn_icon"]
    originals = {}
    slide_keys.each do |key|
      next unless @sprites[key] && !@sprites[key].disposed?
      originals[key] = @sprites[key].x
    end
    offset = -40
    frames = 10
    frames.times do |i|
      t = (i + 1).to_f / frames
      f = t * t
      overlay.opacity = (255 * f).to_i
      slide = (offset * f).to_i
      slide_keys.each do |key|
        next unless originals[key]
        @sprites[key].x = originals[key] + slide
      end
      Graphics.update
      Input.update
    end
    overlay.bitmap.dispose
    overlay.dispose
  end

  def hide_sprites
    @sprites.each_value do |spr|
      next unless spr && !spr.disposed?
      spr.visible = false
    end
  end

  def show_sprites
    @sprites.each_value do |spr|
      next unless spr && !spr.disposed?
      spr.visible = true
    end
    # Redesenhar título (pode ter mudado se voltou de busca)
    bmp = @sprites["title"].bitmap
    bmp.clear
    REVisualTheme.draw_header_band(bmp, 8, 3, Graphics.width - 16, 47)
    pbSetSystemFont(bmp)
    bmp.font.size = RE_TITLE_FONT
    tc = Color.new(*RE_TITLE_COLOR)
    ts = Color.new(*RE_TITLE_SHADOW)
    label = @searchResults ? _INTL("POKÉDEX — Busca") : _INTL("POKÉDEX")
    REPixelUI.draw_text_positions(bmp, [
      [label, RE_TEXT_LEFT, 10, 0, tc, ts]
    ])
    REVisualTheme.draw_hline(bmp, RE_TEXT_LEFT - 4, 44, RE_LIST_WIDTH - 10)
    # Contagem atualizada
    seen = 0; owned = 0
    @dexlist.each do |e|
      seen += 1 if $player.pokedex.seen?(e[:species])
      owned += 1 if $player.pokedex.owned?(e[:species])
    end
    bmp.font.size = RE_SMALL_FONT
    dc = Color.new(*RE_DESC_COLOR)
    ds = Color.new(*RE_DESC_SHADOW)
    count_text = _INTL("Vistos: {1}  Capturados: {2}", seen, owned)
    REPixelUI.draw_text_positions(bmp, [
      [count_text, Graphics.width - 12, 14, 1, dc, ds]
    ])
  end

  def dispose_all
    return if @disposed
    @disposed = true
    @sprites.each_value do |spr|
      next unless spr && !spr.disposed?
      spr.bitmap.dispose if spr.bitmap && !spr.bitmap.disposed?
      spr.dispose
    end
    @viewport.dispose unless @viewport.disposed?
  end

  # Compatibilidade
  def pbUpdate; end
  def pbRefresh
    build_dex_list unless @searchResults
    draw_items
    draw_info
  end
end
