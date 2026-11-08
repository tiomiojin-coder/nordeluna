# Nordeluna integration for Voltseon's Pause Menu 2.2.
# Keep original artwork and carousel, including all MenuHandlers entries.
class PokemonSystem
  def current_menu_theme
    value = @current_menu_theme
    value.is_a?(Integer) && value.between?(0, MENU_TEXTCOLOR.length - 1) ? value : DEFAULT_MENU_THEME
  end

  def current_menu_theme=(value)
    @current_menu_theme = value.is_a?(Integer) ? value.clamp(0, MENU_TEXTCOLOR.length - 1) : DEFAULT_MENU_THEME
  end

  alias nordeluna_vpm_theme_path from_current_menu_theme
  def from_current_menu_theme(data, default = nil)
    path = nordeluna_vpm_theme_path(data, default)
    return path unless data.is_a?(String) && data.start_with?("menu_")
    return path if pbResolveBitmap(MENU_FILE_PATH + path)
    fallback = case data
               when /online|friend|chat/ then "menu_pokegear"
               when /performance|controls/ then "menu_options"
               when /mission|quest|journal|arquivo|message/ then "menu_pokedex"
               when /music/ then "menu_pokegear"
               when /craft|shop/ then "menu_bag"
               when /achievement/ then "menu_trainer_card"
               else "menu_debug"
               end
    nordeluna_vpm_theme_path(fallback)
  end
end

# The existing options screen expects an array of labels for an EnumOption.
MenuHandlers.add(:options_menu, :menu_theme, {
  "name" => _INTL("Tema do menu"), "order" => 200, "type" => EnumOption,
  "parameters" => (1..MENU_TEXTCOLOR.length).map { |n| _INTL("Tema {1}", n) },
  "description" => _INTL("Escolha a aparencia do menu VPM."),
  "get_proc" => proc { next $PokemonSystem.current_menu_theme },
  "set_proc" => proc { |value, _scene| $PokemonSystem.current_menu_theme = value }
})

class PokemonPauseMenu
  alias nordeluna_vpm_initialize initialize
  def initialize(scene)
    # Calls from events/other plugins must not open the retired book interface.
    scene = VoltseonsPauseMenu_Scene.new if scene.is_a?(PokemonPauseMenu_Scene)
    nordeluna_vpm_initialize(scene)
  end

  def pbStartPokemonMenu
    $player.update_party_time if $player.respond_to?(:update_party_time)
    begin
      @scene.pbStartScene
      @scene.update
    ensure
      @scene.pbEndScene
      $game_temp.in_menu = false
      $player.last_update_time(System.uptime) if $player.respond_to?(:last_update_time)
    end
  end
end

class VoltseonsPauseMenu_Scene
  def terminated?; !!@has_terminated; end

  def update
    loop do
      Graphics.update
      Input.update
      @pause_menu.update
      # A save/fly/quit handler can end the scene itself. Never update disposed
      # sprites or components after that callback returns.
      break if @has_terminated || @should_exit
      @components.each(&:update)
      pbUpdateSpriteHash(@sprites)
      pbUpdateSceneMap
      pbRefresh
    end
    unless @has_terminated
      pbSEPlay(MENU_CLOSE_SOUND)
      pbHideMenu
    end
    pbEndScene
  end

  alias nordeluna_vpm_end_scene pbEndScene
  def pbEndScene
    return if @has_terminated
    @should_exit = true
    %w[backshade location].each do |key|
      sprite = @sprites && @sprites[key]
      next unless sprite && !sprite.disposed? && sprite.bitmap
      sprite.bitmap.dispose unless sprite.bitmap.disposed?
      sprite.bitmap = nil
    end
    nordeluna_vpm_end_scene
  end
end
