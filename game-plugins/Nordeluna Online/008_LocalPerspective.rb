# Presentation only. Battle indices, RNG, choices and checksums stay canonical.
module NordelunaOnline
  class LocalBattleView
    INDEX_METHODS = %i[pbSideSize pbParty pbPartyOrder pbPartyStarts pbPlayerDisplayParty
      pbTeamIndexRangeFromBattlerIndex pbTeamLengthFromBattlerIndex
      pbGetOwnerIndexFromBattlerIndex pbRegisteredMegaEvolution? pbCanShift?
      pbCanChooseMove? pbCanShowCommands? pbCanShowFightMenu? pbCanSwitch?
      pbCanSwitchIn? pbCanChooseNonActive? pbRegisterMove pbRegisterSwitch
      pbRegisterMegaEvolution pbAutoChooseMove pbNumPositions
      allSameSideBattlers allOtherSideBattlers pbGetOpposingIndicesInOrder]
    attr_reader :canonical, :side
    def initialize(battle, side)
      @canonical = battle
      @side = side
      @views = {}
    end
    def index(value)
      value.is_a?(Integer) && value >= 0 ? value ^ @side : value
    end
    def wrap(value)
      return @views[value.object_id] ||= LocalBattlerView.new(value, self) if value.is_a?(Battle::Battler)
      return value.map { |entry| wrap(entry) } if value.is_a?(Array)
      return value.map { |entry| wrap(entry) } if value.is_a?(Enumerator)
      value
    end
    def unwrap(value)
      return value.canonical if value.is_a?(LocalBattlerView)
      return value.map { |entry| unwrap(entry) } if value.is_a?(Array)
      value
    end
    def battlers
      list = @canonical.battlers
      Array.new(list.length) { |i| wrap(list[index(i)]) }
    end
    def player; @side == 1 ? @canonical.opponent : @canonical.player; end
    def opponent; @side == 1 ? @canonical.player : @canonical.opponent; end
    def party1; @canonical.pbParty(index(0)); end
    def party2; @canonical.pbParty(index(1)); end
    def sideSizes; @side == 1 ? @canonical.sideSizes.reverse : @canonical.sideSizes; end
    def opposes?(a, b = 0); (a % 2) != (b % 2); end
    def pbPlayerBattlerCount; @canonical.pbSideSize(index(0)); end
    def pbOpposingBattlerCount; @canonical.pbSideSize(index(1)); end
    def method_missing(name, *args, &block)
      mapped = args.map { |arg| unwrap(arg) }
      if INDEX_METHODS.include?(name)
        mapped[0] = index(mapped.empty? ? 0 : mapped[0])
      elsif %i[pbMoveCanTarget? nearBattlers? pbRegisterTarget].include?(name)
        2.times { |i| mapped[i] = index(mapped[i]) }
      end
      callback = block && proc { |*values| block.call(*values.map { |v| wrap(v) }) }
      result = @canonical.public_send(name, *mapped, &callback)
      return result.map { |i| index(i) } if name == :pbGetOpposingIndicesInOrder
      wrap(result)
    end
    def respond_to_missing?(name, private_methods = false)
      @canonical.respond_to?(name, private_methods) || super
    end
  end

  # Gen9 abilities also access scene.sprites directly with canonical indices.
  class LocalSpriteMap
    include Enumerable
    def initialize(sprites, view); @sprites = sprites; @view = view; end
    def key(value)
      return value unless value.is_a?(String)
      if value =~ /\A(pokemon|shadow|dataBox|abilityBar|partyBar)_(\d+)\z/
        return "#{$1}_#{@view.index($2.to_i)}"
      elsif value =~ /\ApartyBall_(\d+)_(\d+)\z/
        return "partyBall_#{@view.index($1.to_i)}_#{$2}"
      end
      value
    end
    def [](value); @sprites[key(value)]; end
    def []=(value, sprite); @sprites[key(value)] = sprite; end
    def key?(value); @sprites.key?(key(value)); end
    def delete(value); @sprites.delete(key(value)); end
    def each
      return enum_for(:each) unless block_given?
      @sprites.each { |name, sprite| yield key(name), sprite }
    end
    def values; @sprites.values; end
    def keys; map { |name, _sprite| name }; end
  end

  class LocalBattlerView
    attr_reader :canonical
    def initialize(battler, view); @canonical = battler; @view = view; end
    def index; @view.index(@canonical.index); end
    def battle; @view; end
    def idxOwnSide; index % 2; end
    def idxOpposingSide; 1 - idxOwnSide; end
    def opposes?(other = 0); (index % 2) != (other % 2); end
    def pbOwnedByPlayer?; index.even?; end
    def method_missing(name, *args, &block)
      @view.wrap(@canonical.public_send(name, *args.map { |arg| @view.unwrap(arg) }, &block))
    end
    def respond_to_missing?(name, private_methods = false)
      @canonical.respond_to?(name, private_methods) || super
    end
  end

  class LocalScene
    FIRST_INDEX = %i[pbRefreshOne pbChangePokemon pbResetCommandsIndex pbCommandMenu
      pbCommandMenuEx pbFightMenu pbPartyScreen pbChooseTarget pbRecall
      pbSelectBattler pbHideCaptureBall pbSafariCommandMenu pbSafariStart]
    attr_reader :view
    def initialize(scene, side); @scene = scene; @side = side; end
    def sprites
      return @scene.sprites unless @view
      LocalSpriteMap.new(@scene.sprites, @view)
    end
    def pbStartBattle(battle)
      @view = LocalBattleView.new(battle, @side)
      @scene.pbStartBattle(@view)
    end
    def method_missing(name, *args, &block)
      mapped = args.map { |arg| @view ? @view.wrap(arg) : arg }
      if @view
        if FIRST_INDEX.include?(name)
          mapped[0] = @view.index(mapped[0])
        elsif name == :pbSwapBattlerSprites
          2.times { |i| mapped[i] = @view.index(mapped[i]) }
        elsif name == :pbShowPartyLineup
          mapped[0] = @view.index(mapped[0])
        elsif name == :pbSendOutBattlers
          mapped[0] = args[0].map { |entry| [@view.index(entry[0]), *entry.drop(1)] }
        elsif name == :pbEndBattle && @side == 1
          mapped[0] = {1 => 2, 2 => 1}.fetch(mapped[0], mapped[0])
        end
      end
      result = @scene.public_send(name, *mapped, &block)
      name == :pbChooseTarget && @view ? @view.index(result) : result
    end
    def respond_to_missing?(name, private_methods = false)
      @scene.respond_to?(name, private_methods) || super
    end
  end

  module PresentLocalSide
    attr_reader :online_side
    def initialize(scene, parties, trainers, session, seed)
      if session.side == 1 && defined?(Battle::Scene) && scene.is_a?(Battle::Scene)
        scene = LocalScene.new(scene, session.side)
      end
      super(scene, parties, trainers, session, seed)
    end
  end
  LinkBattle.prepend(PresentLocalSide)

  module LocalBattlerNames
    def pbThis(lower_case = false)
      if @battle.respond_to?(:online_side) && @battle.online_side == 1
        return name if index.odd?
        return lower_case ? _INTL("the opposing {1}", name) : _INTL("The opposing {1}", name)
      end
      super
    end
  end
  Battle::Battler.prepend(LocalBattlerNames)
end
