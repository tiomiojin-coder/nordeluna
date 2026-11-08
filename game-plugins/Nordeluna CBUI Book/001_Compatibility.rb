# Native CBUI graphics and 2x2 controllers, with Nordeluna battle effects.
# The plugin name is retained for dependency compatibility; the book is retired.
module NordelunaCBUIBook
  def self.below(klass, owner, name)
    method = klass.instance_method(name)
    method = method.super_method until !method || method.owner == owner
    raise "Missing Nordeluna compatibility hook: #{name}" unless method && method.super_method
    method.super_method
  end

  SCENE = [:pbInitSprites, :pbCommandMenuEx, :pbFightMenu].to_h do |name|
    [name, below(Battle::Scene, NordelunaBattle::Scene, name)]
  end
  DATA_BOX = [:initializeOtherGraphics, :draw_background, :draw_name, :draw_level,
              :draw_gender, :draw_status, :draw_shiny_icon, :draw_owned_icon,
              :draw_special_form_icon, :pbDrawNumber].to_h do |name|
    [name, below(Battle::Scene::PokemonDataBox, NordelunaBattle::DataBox, name)]
  end

  module FightTypes
    def refreshSelection
      super
      return unless @buttonBitmap && @buttons
      # Original red/blue sheets have fewer rows than Nordeluna has types.
      # Keep those optional themes usable with custom types, without changing
      # the move's actual type, damage or type icon.
      rows = @buttonBitmap.height / self.class::BUTTON_HEIGHT
      @buttons.each do |button|
        next if !button || button.src_rect.y < rows * self.class::BUTTON_HEIGHT
        button.src_rect.y = 0
      end
    end
  end

  module Scene
    def pbInitSprites
      NordelunaCBUIBook::SCENE[:pbInitSprites].bind_call(self)
      # Keep native message graphics, colours and bitmap ownership.
      # The book header and technique overlay are retired.
    end

    def pbCommandMenuEx(*args, &block)
      NordelunaCBUIBook::SCENE[:pbCommandMenuEx].bind_call(self, *args, &block)
    end

    def pbFightMenu(*args, &block)
      NordelunaCBUIBook::SCENE[:pbFightMenu].bind_call(self, *args, &block)
    end

    # Hooks called by the underlying presentation module.
    def nl_update_presentation; end
    def nl_show_technique(*args); end
  end

  module DataBox
    NordelunaCBUIBook::DATA_BOX.each do |name, implementation|
      define_method(name) do |*args, &block|
        if respond_to?(:ndb_custom?) && ndb_custom?
          # Selected databox styles own their backgrounds, bars and text. Keep
          # the existing native bypass only for the unchanged default style.
          super(*args, &block)
        else
          implementation.bind_call(self, *args, &block)
        end
      end
    end
  end
end

Battle::Scene::FightMenu.prepend(NordelunaCBUIBook::FightTypes)
Battle::Scene::PokemonDataBox.prepend(NordelunaCBUIBook::DataBox)
Battle::Scene.prepend(NordelunaCBUIBook::Scene)
