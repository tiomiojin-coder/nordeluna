class PokemonGlobalMetadata
  attr_accessor :nordeluna_owned_outfits
end

module NordelunaOnline
  class WardrobePreview < Sprite
    def initialize(viewport,id)
      super(viewport)
      row=Wardrobe.validate!(id)
      base=GameData::PlayerMetadata.get($player.character_ID).walk_charset
      self.bitmap=Bitmap.new(pbResolveBitmap("Graphics/Characters/#{base}_#{row[:outfit]}"))
      w,h=bitmap.width/4,bitmap.height/4
      self.src_rect.set(0,0,w,h);self.ox=w/2;self.oy=h/2
    end
    def dispose
      bitmap.dispose if bitmap && !bitmap.disposed?
      super
    end
  end
  module Wardrobe
    # Register finished artwork only. IDs are permanent, as they appear in receipts.
    CATALOG_PATH='Plugins/Nordeluna Online/assets/outfits.json'
    class << self
      def catalog
        return @catalog if @catalog
        raw=File.file?(CATALOG_PATH) ? JSON.parse(File.binread(CATALOG_PATH)) : {}
        raise Error,'Catalogo de roupas invalido.' unless raw.is_a?(Hash) && raw.length<=100
        @catalog=raw.each_with_object({}) do |(id,row),result|
          valid=id.match?(/\A[A-Z][A-Z0-9_]{0,63}\z/) && row.is_a?(Hash) &&
            row['name'].is_a?(String) && row['name'].length.between?(1,48) &&
            row['outfit'].is_a?(Integer) && row['outfit'].between?(1,999) &&
            row['characters'].is_a?(Array) && !row['characters'].empty? && row['characters'].all? { |n| n.is_a?(Integer) && n>0 }
          raise Error,'Entrada de roupa invalida.' unless valid
          result[id]={name:row['name'],outfit:row['outfit'],characters:row['characters']}
        end
      end
      def story?
        return false unless defined?(FlashbackSystem)
        !!((FlashbackSystem.respond_to?(:in_flashback?) && FlashbackSystem.in_flashback?) ||
          (FlashbackSystem.respond_to?(:current_perspective) && FlashbackSystem.current_perspective))
      end
      def online_allowed!
        raise Error,'O Online fica indisponivel durante o flashback. Volte a historia do protagonista.' if story?
      end
      def owned
        value=$PokemonGlobal.nordeluna_owned_outfits
        value.is_a?(Array) ? value : []
      end
      def definition(id)
        row=catalog[id]
        raise VersionMismatch,'Esta roupa ainda nao foi instalada. Atualize o jogo antes de comprar.' unless row
        row
      end
      def validate!(id)
        row=definition(id)
        raise VersionMismatch,'Esta roupa nao serve para este protagonista.' unless row[:characters].include?($player.character_ID)
        raise Error,'Numero de roupa invalido.' unless row[:outfit].is_a?(Integer) && row[:outfit]>0
        meta=GameData::PlayerMetadata.get($player.character_ID)
        # Do not sell a walking-only skin which vanishes when running or surfing.
        %i[walk_charset run_charset cycle_charset surf_charset dive_charset fish_charset surf_fish_charset].each do |key|
          next unless meta.respond_to?(key)
          base=meta.public_send(key)
          next if !base || base.empty?
          raise VersionMismatch,"Falta o sprite da roupa: #{base}_#{row[:outfit]}." unless pbResolveBitmap("Graphics/Characters/#{base}_#{row[:outfit]}")
        end
        row
      end
      def unlock(id)
        validate!(id)
        $PokemonGlobal.nordeluna_owned_outfits=(owned+[id]).uniq
      end
      def equip(id)
        online_allowed!
        raise Error,'A roupa ainda nao foi comprada neste save.' if id && !owned.include?(id)
        value=id ? validate!(id)[:outfit] : 0
        $player.outfit=value
        $game_player.refresh if $game_player
        true
      end
      def open
        online_allowed!
        rows=owned.select { |id| catalog.key?(id) }
        labels=['Roupa original']+rows.map { |id| definition(id)[:name] }+['Voltar']
        loop do
          chosen=OnlineUI.choose('Meu armario',labels,labels.length-1,'Roupas da campanha / use as setinhas')
          return if chosen==labels.length-1
          id=chosen==0 ? nil : rows[chosen-1]
          equip(id)
          pbMessage(_INTL('Roupa vestida! Ela sera mantida ao salvar sua aventura.'))
        end
      rescue Error => error
        pbMessage(_INTL('{1}',error.message))
      end
    end
  end

  # All routes, including event script calls, share the story restriction.
  module StoryTransportGuard
    def request(url,data)
      Wardrobe.online_allowed! unless data['action']=='map_leave'
      super
    end
  end
  singleton_class.prepend(StoryTransportGuard)
  module StoryHubGuard
    def open
      Wardrobe.online_allowed!
      super
    rescue Error => error
      pbMessage(_INTL('{1}',error.message))
    end
  end
  SocialHub.singleton_class.prepend(StoryHubGuard)

  module StoryEntryGuard
    def execute_start(*args)
      NordelunaOnline::MapChannel.disconnect if NordelunaOnline::MapChannel.managed? || NordelunaOnline::MapChannel.active?
      super
    end
    def enter_perspective(*args)
      NordelunaOnline::MapChannel.disconnect if NordelunaOnline::MapChannel.managed? || NordelunaOnline::MapChannel.active?
      super
    end
  end
  def self.install_story_guard
    return unless defined?(FlashbackSystem)
    FlashbackSystem.singleton_class.prepend(StoryEntryGuard) unless FlashbackSystem.singleton_class.ancestors.include?(StoryEntryGuard)
  end
  install_story_guard
end
EventHandlers.add(:on_frame_update,:nordeluna_story_guard,proc { NordelunaOnline.install_story_guard })

# RPG Maker event command > Script, for either a wardrobe or a clothing shop.
def pbNordelunaWardrobe
  NordelunaOnline::Wardrobe.open
end
