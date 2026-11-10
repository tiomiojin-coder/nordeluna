class PokemonGlobalMetadata
  attr_accessor :nordeluna_gift_pending, :nordeluna_gift_receipts
end

module NordelunaOnline
  module Gifts
    class << self
      def pending; $PokemonGlobal.nordeluna_gift_pending; end
      def receipts; $PokemonGlobal.nordeluna_gift_receipts || []; end
      def api(action, data={})
        NordelunaOnline.request(NordelunaOnline.server,data.merge('action'=>action,'account'=>Identity.ensure_registered))
      end
      def save!
        Areas.checked_save!
        saved=Marshal.load(File.binread(SaveData::FILE_PATH))[:global_metadata]
        raise Error,'O resgate nao foi confirmado no save.' unless saved &&
          saved.nordeluna_gift_pending==pending && saved.nordeluna_gift_receipts==$PokemonGlobal.nordeluna_gift_receipts &&
          saved.nordeluna_owned_outfits==$PokemonGlobal.nordeluna_owned_outfits
      end
      def identifier(value)
        raise Error,'ID de recompensa invalido.' unless value.is_a?(String) && value.match?(/\A[A-Z][A-Z0-9_]{0,63}\z/)
        value.to_sym
      end
      def integer(value, low, high)
        raise Error,'Quantidade de presente invalida.' unless value.is_a?(Integer) && value.between?(low,high)
        value
      end
      def validate_rewards(rows)
        raise Error,'Pacote de presente invalido.' unless rows.is_a?(Array) && rows.length.between?(1,10)
        rows.each do |row|
          raise Error,'Recompensa invalida.' unless row.is_a?(Hash)
          case row['kind']
          when 'item'
            raise VersionMismatch,'Este item nao existe nesta versao do jogo.' unless GameData::Item.exists?(identifier(row['id']))
            integer(row['quantity'],1,999)
          when 'money' then integer(row['amount'],1,9999999)
          when 'outfit' then Wardrobe.validate!(identifier(row['id']).to_s)
          when 'pokemon'
            species=identifier(row['species']);form=integer(row['form'],0,999)
            raise VersionMismatch,'Esta especie nao existe nesta versao do jogo.' unless GameData::Species.exists?(species)
            data=GameData::Species.get_species_form(species,form)
            raise VersionMismatch,'Esta forma nao existe nesta versao do jogo.' unless data && data.form==form
            integer(row['level'],1,100)
            raise Error,'Condicao shiny invalida.' unless [true,false].include?(row['shiny'])
            raise Error,'Condicao de ovo invalida.' unless [true,false].include?(row.fetch('egg',false))
            raise VersionMismatch,'Item do Pokemon nao encontrado.' if row['item'] && !GameData::Item.exists?(identifier(row['item']))
            if row['moves']
              raise Error,'Golpes de presente invalidos.' unless row['moves'].is_a?(Array) && row['moves'].length.between?(1,4) && row['moves'].uniq==row['moves']
              row['moves'].each { |id| raise VersionMismatch,'Golpe nao encontrado nesta versao.' unless GameData::Move.exists?(identifier(id)) }
            end
          else raise Error,'Tipo de presente desconhecido.'
          end
        end
        raise Error,'Presente com Pokemon demais.' if rows.count { |r| r['kind']=='pokemon' }>6
        raise Error,'O valor total deste presente excede o limite de dinheiro do jogo.' if rows.select { |r| r['kind']=='money' }.sum { |r| r['amount'] }>Settings::MAX_MONEY
        if Settings.const_defined?(:BAG_MAX_PER_SLOT)
          rows.select { |r| r['kind']=='item' }.group_by { |r| r['id'] }.each_value do |items|
            raise Error,'A quantidade deste item excede o limite da mochila.' if items.sum { |r| r['quantity'] }>Settings::BAG_MAX_PER_SLOT
          end
        end
        rows
      end
      def validate_claim(ticket)
        raise Error,'Recibo de presente invalido.' unless ticket.is_a?(Hash) && ticket['id'].is_a?(String) &&
          ticket['id'].match?(/\A[0-9a-f]{32}\z/) && %w[reserved issued delivered].include?(ticket['state']) &&
          ticket['title'].is_a?(String) && ticket['title'].length.between?(1,70)
        validate_rewards(ticket['rewards'])
        ticket
      end
      def reward_labels(rows)
        validate_rewards(rows).map do |row|
          case row['kind']
          when 'item' then "#{row['quantity']}x #{GameData::Item.get(row['id']).name}"
          when 'money' then "$ #{row['amount']}"
          when 'outfit' then "Roupa: #{Wardrobe.definition(row['id'])[:name]}"
          else "#{row['egg'] ? 'Ovo de ' : ''}#{GameData::Species.get_species_form(row['species'],row['form']).name} / Nv. #{row['level']}#{row['shiny'] ? ' / Shiny' : ''}"
          end
        end
      end
      def make_plan(rows)
        validate_rewards(rows).map do |row|
          next row.dup unless row['kind']=='pokemon'
          pokemon=Pokemon.new(row['species'].to_sym,row['level'],Pokemon::Owner.new(0x4E4F5244,'Nordeluna',2,0))
          # Avoid form callbacks/Pokedex changes before the gift is delivered.
          pokemon.form_simple=row['form']
          pokemon.shiny=row['shiny']
          pokemon.item=row['item'].to_sym if row['item']
          pokemon.reset_moves
          pokemon.moves=row['moves'].map { |id| Pokemon::Move.new(id.to_sym) } if row['moves']
          pokemon.obtain_method=4
          pokemon.obtain_text='Presente Nordeluna'
          pokemon.calc_stats;pokemon.heal
          # The battle/trade codec correctly rejects eggs. The local gift plan
          # stores the base Pokemon and turns it into an egg only on delivery.
          {'kind'=>'pokemon','pokemon'=>PokemonCodec.encode(pokemon),'egg'=>!!row['egg']}
        end
      end
      def prepare(ticket)
        validate_claim(ticket)
        raise Error,'Recupere o presente pendente antes de iniciar outro.' if pending
        raise Error,'Este presente ja foi iniciado em outro save. Use o save original para recuperar.' unless ticket['state']=='reserved'
        previous=pending
        $PokemonGlobal.nordeluna_gift_pending={'url'=>NordelunaOnline.server,'account'=>Identity.ensure_registered['id'],
          'claim'=>ticket,'plan'=>make_plan(ticket['rewards'])}
        begin
          save!
        rescue StandardError
          $PokemonGlobal.nordeluna_gift_pending=previous
          raise
        end
      end
      def capacity(plan)
        bag=Marshal.load(Marshal.dump($bag))
        money=$player.money
        pokes=[]
        plan.each do |row|
          case row['kind']
          when 'item'
            raise Error,'Libere espaco na mochila e use Recuperar presente.' unless bag.can_add?(row['id'],row['quantity']) && bag.add(row['id'],row['quantity'])
          when 'money'
            money+=row['amount']
            raise Error,'O dinheiro ultrapassaria o limite. Gaste um pouco e recupere o presente.' if money>Settings::MAX_MONEY
          when 'outfit'
            Wardrobe.validate!(row['id'])
          when 'pokemon'
            pokemon=PokemonCodec.decode(row['pokemon'])
            if row['egg']
              pokemon.steps_to_hatch=[pokemon.species_data.hatch_steps,1].max
              pokemon.name=_INTL('Egg')
              pokemon.obtain_method=1
            end
            pokes<<pokemon
          else raise Error,'Plano de presente invalido.'
          end
        end
        positions=[]
        needed=[pokes.length-[Settings::MAX_PARTY_SIZE-$player.party.length,0].max,0].max
        if needed>0
          $PokemonStorage.maxBoxes.times do |box|
            $PokemonStorage.maxPokemon(box).times { |slot| positions<<[box,slot] if !$PokemonStorage[box,slot] && positions.length<needed }
          end
        end
        raise Error,'Equipe e boxes sem espaco. Libere espaco e use Recuperar presente.' if positions.length<needed
        [bag,money,pokes,positions]
      end
      def acknowledge(receipt)
        return if receipt['acked'] || receipt['url']!=NordelunaOnline.server
        api('gift_ack','claim'=>receipt['id'])
        receipt['acked']=true
        begin
          save!
        rescue StandardError
          receipt['acked']=false
          raise
        end
      end
      def deliver
        ticket=pending
        raise Error,'Nenhum presente pendente neste save.' unless ticket
        raise Error,'Volte ao servidor original deste presente para recuperar.' unless ticket['url']==NordelunaOnline.server && ticket['account']==Identity.ensure_registered['id']
        validate_claim(ticket['claim'])
        bag,money,pokes,positions=capacity(ticket['plan'])
        remote=validate_claim(api('gift_begin','claim'=>ticket['claim']['id']))
        raise Error,'O recibo retornado nao corresponde ao presente.' unless remote['id']==ticket['claim']['id'] && remote['rewards']==ticket['claim']['rewards']
        raise Error,'Este resgate ja foi confirmado. Use o save original.' if remote['state']=='delivered'
        old_party=$player.party.dup;old_bag=$bag;old_money=$player.money;old_receipts=receipts
        old_outfits=$PokemonGlobal.nordeluna_owned_outfits
        old_dex=$player.respond_to?(:pokedex) ? $player.pokedex : nil
        occupied=[]
        receipt={'id'=>remote['id'],'title'=>remote['title'],'url'=>NordelunaOnline.server,'time'=>Time.now.to_i,'acked'=>false}
        begin
          $bag=bag;$player.money=money
          ticket['plan'].each { |row| Wardrobe.unlock(row['id']) if row['kind']=='outfit' }
          $player.instance_variable_set(:@pokedex,Marshal.load(Marshal.dump(old_dex))) if old_dex
          pokes.each do |pokemon|
            if old_dex && !pokemon.egg?
              $player.pokedex.register(pokemon)
              $player.pokedex.set_owned(pokemon.species)
            end
            if $player.party.length<Settings::MAX_PARTY_SIZE
              $player.party<<pokemon
            else
              box,slot=positions.shift
              occupied<<[box,slot]
              $PokemonStorage[box,slot]=pokemon
            end
          end
          $PokemonGlobal.nordeluna_gift_receipts=old_receipts+[receipt]
          $PokemonGlobal.nordeluna_gift_pending=nil
          save!
        rescue StandardError
          $player.party.replace(old_party);$bag=old_bag;$player.money=old_money
          $PokemonGlobal.nordeluna_owned_outfits=old_outfits
          $player.instance_variable_set(:@pokedex,old_dex) if old_dex
          occupied.each { |box,slot| $PokemonStorage[box,slot]=nil }
          $PokemonGlobal.nordeluna_gift_receipts=old_receipts
          $PokemonGlobal.nordeluna_gift_pending=ticket
          raise
        end
        # Delivery is durable now. A failed acknowledgement must never award twice.
        begin
          acknowledge(receipt)
        rescue StandardError => error
          NordelunaOnline.record_online_error(error,'gift_ack')
        end
        true
      end
      def recover
        receipts.each { |receipt| acknowledge(receipt) unless receipt['acked'] }
        if pending
          deliver
          pbMessage(_INTL('Presente recebido! O jogo foi salvo.'))
          return
        end
        rows=api('gift_history')['claims']
        rows=rows.select { |row| row['state']=='reserved' }
        return pbMessage(_INTL('Nenhum presente pendente neste save.')) if rows.empty?
        n=OnlineUI.choose('Presentes reservados',rows.map { |row| row['title'] }+['Voltar'],rows.length)
        return unless n>=0 && n<rows.length
        prepare(rows[n]);deliver
        pbMessage(_INTL('Presente recuperado e salvo!'))
      end
      def redeem
        return recover if pending
        code=pbMessageFreeText(_INTL('Digite ou cole o codigo do presente:'),'',false,32).strip.upcase
        return if code.empty?
        reply=api('gift_preview','code'=>code)
        if reply['claim']
          return pbMessage(_INTL('Este codigo ja tem um resgate nesta conta. Consulte o historico ou recupere o presente.'))
        end
        preview=reply['preview']
        raise Error,'Previa de presente invalida.' unless preview.is_a?(Hash) && preview['title'].is_a?(String)
        labels=reward_labels(preview['rewards'])
        loop do
          n=OnlineUI.choose(preview['title'],labels+['Confirmar resgate','Voltar'],labels.length+1,'Uma vez por conta / salva automaticamente')
          return if n==labels.length+1
          break if n==labels.length
        end
        ticket=api('gift_reserve','code'=>code)['claim']
        raise Error,'O presente mudou. Consulte a previa novamente.' unless ticket && ticket['rewards']==preview['rewards']
        prepare(ticket);deliver
        pbMessage(_INTL('Presente recebido! O jogo foi salvo.'))
      end
      def open
        health=NordelunaOnline.test_connection(false)
        raise VersionMismatch,'Presentes precisam do servidor revisao 8.' unless health['revision'].to_i>=8
        Identity.ensure_registered
        loop do
          n=OnlineUI.choose('Presentes',['Resgatar codigo','Recuperar presente','Historico de resgates','Voltar'],3,
            pending ? 'Existe um presente pendente neste save' : 'Itens e Pokemon enviados pelo Nordeluna')
          case n
          when 0 then redeem
          when 1 then recover
          when 2
            rows=api('gift_history')['claims']
            labels=rows.map { |row| "#{row['title']} / #{ {'reserved'=>'Reservado','issued'=>'Entrega iniciada','delivered'=>'Recebido'}[row['state']] }" }
            OnlineUI.choose('Historico',labels+['Voltar'],labels.length,'Um resgate por conta / nick pode mudar')
          else return
          end
        end
      rescue Error => error
        pbMessage(_INTL('Presentes: {1}',error.message))
      rescue StandardError => error
        NordelunaOnline.record_online_error(error,'gifts')
        pbMessage(_INTL('Nao foi possivel concluir. Se o presente foi reservado, use Recuperar presente.'))
      end
    end
  end
end
