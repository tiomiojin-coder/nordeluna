# encoding: UTF-8
module NordelunaMudTerrain
  SOUND_ENABLED = true
  VISUAL_ENABLED = true
  SOUND_VOLUME = 42
  ASSET_ROOT = "Plugins/Nordeluna Mud Terrain/assets"
  EFFECT_DURATION = 0.85

  # Respingos em pixel art e uma marca de pisada que desaparece no chão.
  # O spriteset do mapa controla a atualização e o descarte deste efeito.
  class FootstepSprite < Sprite
    def initialize(map, tile_x, tile_y, foot)
      super(Spriteset_Map.viewport)
      @map, @tile_x, @tile_y = map, tile_x, tile_y
      @foot = foot.even? ? -4 : 4
      @started_at = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      self.bitmap = Bitmap.new(48, 32)
      self.ox = 24
      self.oy = 28
      @dark = Color.new(64, 53, 34)
      @mud = Color.new(113, 88, 49)
      @wet = Color.new(164, 134, 76)
      update
    end

    def update
      return if disposed?
      if defined?(NordelunaPerformance) && NordelunaPerformance.level(:decorations)==0
        dispose
        return
      end
      elapsed = [Process.clock_gettime(Process::CLOCK_MONOTONIC) - @started_at, 0.0].max
      if elapsed >= EFFECT_DURATION
        dispose
        return
      end
      super
      self.x = ((@tile_x * Game_Map::REAL_RES_X - @map.display_x) / Game_Map::X_SUBPIXELS.to_f).round + 16
      self.y = ((@tile_y * Game_Map::REAL_RES_Y - @map.display_y) / Game_Map::Y_SUBPIXELS.to_f).round + 32
      self.z = self.y
      self.opacity = (180 * (1.0 - elapsed / EFFECT_DURATION)).round
      bitmap.clear
      x = 24 + @foot
      y = 25
      bitmap.fill_rect(x - 3, y, 6, 3, @dark)
      bitmap.fill_rect(x - 2, y - 1, 4, 4, @mud)
      bitmap.fill_rect(x - 2, y, 3, 1, @wet)
      if elapsed < 0.3
        spread = (elapsed * 13).round
        bitmap.fill_rect(x - 6 - spread, y + 1, 3, 1, @mud)
        bitmap.fill_rect(x + 4 + spread, y + 1, 3, 1, @mud)
        [-22, -11, 12, 23].each_with_index do |velocity, i|
          dx = (velocity * elapsed).round
          dy = ((-30 - i * 4) * elapsed + 110 * elapsed * elapsed).round
          bitmap.fill_rect(x + dx, y + dy, 2, 2, i.even? ? @mud : @wet)
        end
      end
      pbDayNightTint(self)
    end

    def dispose
      return if disposed?
      bitmap.dispose if bitmap && !bitmap.disposed?
      super
    end
  end

  def self.play_footstep(event)
    return if event != $game_player || !$scene.is_a?(Scene_Map)
    return if $game_temp.in_menu || $game_temp.in_battle || event.move_route_forcing
    return if $PokemonGlobal&.surfing || $PokemonGlobal&.diving
    return if event.pbTerrainTag.id != TERRAIN_ID
    @step_number = (@step_number || 0) + 1
    if SOUND_ENABLED
      path = "#{ASSET_ROOT}/mud_step_#{(@step_number % 3) + 1}.wav"
      volume = (SOUND_VOLUME * $PokemonSystem.sevolume / 100.0).round
      # Caminho direto dos assets do plugin; respeita o volume de SE do jogador.
      Audio.se_play(path, volume, 98 + (@step_number % 3) * 2) if volume > 0
    end
    if VISUAL_ENABLED && (!defined?(NordelunaPerformance) || NordelunaPerformance.decoration_step?(@step_number))
      spriteset = $scene.spriteset(event.map_id)
      spriteset&.addUserSprite(FootstepSprite.new(event.map, event.x, event.y, @step_number))
    end
  end
end

EventHandlers.add(:on_step_taken, :nordeluna_mud_footsteps,
  proc { |event| NordelunaMudTerrain.play_footstep(event) }
)
