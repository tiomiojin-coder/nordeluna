module NordelunaAtmosphere
  class Renderer
    attr_reader :disposed

    def initialize
      @disposed = false
      @rng = Random.new
      @assets = {}
      @particles = []
      @lights = {}
      @sound = Soundscape.new
      # Below pictures (200), transitions (500), UI and the tactical lantern (999).
      @viewport = Viewport.new(0, 0, Graphics.width, Graphics.height)
      @viewport.z = 90
      @warm = Sprite.new(@viewport)
      @warm.bitmap = Bitmap.new(1, 1)
      @warm.bitmap.fill_rect(0, 0, 1, 1, Color.new(255, 184, 84))
      @warm.opacity = 0
      @fog = Plane.new(@viewport)
      @fog.bitmap = asset(:fog)
      @fog.opacity = 0
      @fog.z = 1
      @fog_detail = Plane.new(@viewport)
      @fog_detail.bitmap = asset(:fog_detail)
      @fog_detail.z = 2
      @fog_detail.zoom_x = @fog_detail.zoom_y = 1.5
      @fog_detail.opacity = 0
      @rays = Sprite.new(@viewport)
      @rays.bitmap = asset(:sunrays)
      @rays.blend_type = 1
      @rays.z = 1
      @rays.opacity = 0
      @fog_level = @warm_level = @ray_level = 0.0
      @last_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      @poll_at = 0
      @fade = 0.0
    end

    def asset(name)
      cached = @assets[name]
      @assets[name] = Bitmap.new("#{ASSET_ROOT}/#{name}.png") if !cached || cached.disposed?
      return @assets[name]
    end

    def update
      return if @disposed
      now = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      dt = [[now - @last_time, 0.0].max, 0.1].min
      @last_time = now
      # The engine updates map sprites behind menus and battle transitions.
      hidden = !$scene.is_a?(Scene_Map) || $game_temp.in_battle || $game_temp.in_menu
      @viewport.visible = !hidden
      return if hidden || !$game_map
      if now >= @poll_at || @map_id != $game_map.map_id
        refresh(now)
        @poll_at = now + 0.5
      end
      @viewport.rect.set(0, 0, Graphics.width, Graphics.height)
      @viewport.ox = $game_screen.shake
      @warm.zoom_x = Graphics.width
      @warm.zoom_y = Graphics.height
      @fade = [@fade + dt * 1.5, 1.0].min
      decorations=defined?(NordelunaPerformance) ? NordelunaPerformance.level(:decorations) : 2
      @fog.visible=@warm.visible=(decorations>0)
      @fog_detail.visible=@rays.visible=(decorations==2)
      if decorations>0
      @warm_level = approach(@warm_level, @state[:warm], dt * 15)
      @fog_level = approach(@fog_level, @state[:fog], dt * 22)
      @ray_level = approach(@ray_level, @state[:rays], dt * 18)
      @warm.opacity = @warm_level
      @fog.opacity = @fog_level
      @fog_detail.opacity = @fog_level * 0.65
      cx, cy = camera
      @fog.ox = (now * 4 + cx * 0.15) % 256
      @fog.oy = (now * 1.5 + cy * 0.15) % 256
      @fog_detail.ox = (-now * 6 + cx * 0.3) % 384
      @fog_detail.oy = (now * 2 + cy * 0.3) % 384
      @rays.zoom_x = (Graphics.width + 32) / 256.0
      @rays.zoom_y = (Graphics.height + 24) / 256.0
      @rays.x = -16 + Math.sin(now * 0.12) * 12
      @rays.y = -12
      @rays.opacity = @ray_level * (0.88 + Math.sin(now * 0.3) * 0.12)
      end
      update_particles(dt, now)
      update_lights(now)
    end

    def approach(current, target, step)
      return target if (target - current).abs <= step
      return current + (target <=> current) * step
    end

    def refresh(now)
      next_state = NordelunaAtmosphere.state
      map_changed = @map_id != $game_map.map_id
      changed = map_changed || !@state ||
                @state.values_at(:particle, :count) != next_state.values_at(:particle, :count)
      @state = next_state
      @map_id = $game_map.map_id
      if map_changed
        @fade = 0.0
        @fog.opacity = 0
        @warm.opacity = 0
        @fog_detail.opacity = @rays.opacity = 0
        @fog_level = @warm_level = @ray_level = 0.0
      end
      reset_particles if changed
      sync_lights
      @sound.update(@state[:sound], @map_id)
    end

    def reset_particles
      @particles.each { |p| p[:sprite].dispose }
      @particles.clear
      @particle_fade = 0.0
      @state[:count].times do
        sprite = Sprite.new(@viewport)
        kind = @state[:particle]
        texture = kind == :leaf ? [:leaf, :leaf, :leaf_gold, :leaf_brown][@rng.rand(4)] : kind
        sprite.bitmap = asset(texture)
        sprite.ox = sprite.bitmap.width / 2
        sprite.oy = sprite.bitmap.height / 2
        depth = [0.55, 0.8, 1.15][@rng.rand(3)]
        sprite.z = depth < 0.8 ? 1 : 4
        sprite.zoom_x = sprite.zoom_y = depth
        # Alpha blending preserves the texture hue on bright map tiles. Additive
        # blending made small colored motes look like identical white specks.
        sprite.blend_type = 0
        @particles << { :sprite => sprite, :x => @rng.rand * Graphics.width,
                        :y => @rng.rand * Graphics.height, :speed => 0.6 + @rng.rand,
                        :phase => @rng.rand * Math::PI * 2, :depth => depth,
                        :flutter => 0.6 + @rng.rand * 1.6 }
      end
      @camera = camera
    end

    def camera
      return [$game_map.display_x.to_f / Game_Map::X_SUBPIXELS,
              $game_map.display_y.to_f / Game_Map::Y_SUBPIXELS]
    end

    def update_particles(dt, now)
      pos = camera
      dx, dy = pos[0] - @camera[0], pos[1] - @camera[1]
      @camera = pos
      kind = @state[:particle]
      @particle_fade = [@particle_fade + dt * 1.8, 1.0].min
      @particles.each do |p|
        wave = Math.sin(now * p[:flutter] + p[:phase])
        gust = 1.0 + Math.sin(now * 0.32) * 0.4 + Math.sin(now * 0.71) * 0.15
        vx = (kind == :leaf ? 14 : 7) * gust
        vy = kind == :leaf ? 12 : -3
        vx, vy = wave * 6, Math.cos(now + p[:phase]) * 3 if kind == :firefly
        p[:x] = (p[:x] + (vx + wave * 3) * p[:speed] * dt - dx * p[:depth] + 16) % (Graphics.width + 32) - 16
        p[:y] = (p[:y] + vy * p[:speed] * dt - dy * p[:depth] + 16) % (Graphics.height + 32) - 16
        sprite = p[:sprite]
        sprite.x, sprite.y = p[:x], p[:y]
        if kind == :leaf
          sprite.angle = wave * 42
          sprite.zoom_x = p[:depth] * (0.3 + Math.cos(now * 2 + p[:phase]).abs * 0.7)
        end
        pulse = (0.5 + 0.5 * Math.sin(now * p[:flutter] + p[:phase])) ** 2
        alpha = case kind
                when :dust then 65 + wave * 18
                when :pollen then 75 + wave * 15
                when :firefly then 25 + pulse * 220
                when :sparkle then 45 + pulse * 175
                else 165
                end
        # Particles dissolve near edges instead of appearing/disappearing abruptly.
        edge = [[p[:x] / 18.0, (Graphics.width - p[:x]) / 18.0,
                 p[:y] / 18.0, (Graphics.height - p[:y]) / 18.0, 1.0].min, 0.0].max
        sprite.opacity = alpha * @fade * @particle_fade * edge
      end
    end

    # Tags can be in the event name or comments of the ACTIVE event page.
    # [AtmoLight:lamp], [AtmoLight:window], [AtmoLight:crystal], [AtmoLight:fire]
    def light_kind(event)
      return nil if !event.list || event.list.empty?
      content = event.name.to_s + " "
      event.list.each do |command|
        content += command.parameters[0].to_s + " " if [108, 408].include?(command.code)
      end
      match = content.match(/\[AtmoLight:(lamp|window|crystal|fire)\]/i)
      return match ? match[1].downcase.to_sym : nil
    end

    def sync_lights
      wanted = {}
      decorations=defined?(NordelunaPerformance) ? NordelunaPerformance.level(:decorations) : 2
      budget=decorations==1 ? [MAX_LIGHTS,4].min : MAX_LIGHTS
      if NordelunaAtmosphere.enabled? && decorations>0
        # Connected maps may be visible before the player steps into them.
        maps = $map_factory ? $map_factory.maps : [$game_map]
        maps.each do |map|
          next if NordelunaAtmosphere.profile_for(map) == :off
          map.events.each do |id, event|
            kind = light_kind(event)
            next if !kind || wanted.length >= budget
            key = [map.map_id, id]
            wanted[key] = [event, kind]
          end
        end
      end
      (@lights.keys - wanted.keys).each { |key| dispose_light(@lights.delete(key)) }
      wanted.each do |key, pair|
        event, kind = pair
        entry = @lights[key]
        if entry && entry[:kind] == kind && entry[:event].equal?(event)
          next
        end
        dispose_light(entry) if entry
        sprite = Sprite.new(@viewport)
        texture = { :lamp => :warm_glow, :window => :window_glow,
                    :crystal => :moon_glow, :fire => :fire_glow }[kind]
        sprite.bitmap = asset(texture)
        sprite.ox = sprite.bitmap.width / 2
        sprite.oy = sprite.bitmap.height / 2
        sprite.z = 3
        sprite.blend_type = 1
        sprite.zoom_x = sprite.zoom_y = 1.0
        core = Sprite.new(@viewport)
        core.bitmap = asset(kind == :crystal ? :sparkle : :light_core)
        core.ox, core.oy = core.bitmap.width / 2, core.bitmap.height / 2
        core.blend_type = 1
        core.z = 4
        @lights[key] = { :event => event, :kind => kind, :sprite => sprite, :core => core }
      end
    end

    def update_lights(now)
      if defined?(NordelunaPerformance) && NordelunaPerformance.level(:decorations)==1
        return if now<(@quality_light_at || 0)
        @quality_light_at=now+1.0/15
      end
      @lights.each_value do |entry|
        event, kind, sprite = entry.values_at(:event, :kind, :sprite)
        sprite.x = event.screen_x
        sprite.y = event.screen_y - 16
        night_only = [:lamp, :window].include?(kind)
        strength = night_only ? @state[:night] : 1.0
        strength = 1.0 if NordelunaAtmosphere.dark?
        flicker = kind == :fire ? Math.sin(now * 9 + event.id) * 10 + Math.sin(now * 17 + event.id * 2) * 5 : Math.sin(now * 1.7 + event.id) * 5
        sprite.opacity = (155 + flicker) * strength * @fade
        if [:crystal, :fire].include?(kind)
          sprite.zoom_x = sprite.zoom_y = 1.0 + flicker * 0.002
        end
        core = entry[:core]
        core.x, core.y = sprite.x, sprite.y
        core.opacity = kind == :window ? 0 : (185 + flicker) * strength * @fade
      end
    end

    def dispose_light(entry)
      entry[:sprite].dispose
      entry[:core].dispose
    end

    def dispose
      return if @disposed
      @sound.stop
      @particles.each { |p| p[:sprite].dispose }
      @lights.each_value { |entry| dispose_light(entry) }
      @warm.bitmap.dispose
      @warm.dispose
      @fog.dispose
      @fog_detail.dispose
      @rays.dispose
      @assets.each_value { |bitmap| bitmap.dispose }
      @assets.clear
      @viewport.dispose
      @disposed = true
    end
  end
end
