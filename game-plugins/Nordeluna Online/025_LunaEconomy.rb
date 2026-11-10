class PokemonGlobalMetadata
  attr_accessor :nordeluna_shop_pending,:nordeluna_battle_reports
end
module NordelunaOnline
  module LunaEconomy
    class << self
      def snapshot; @snapshot if @snapshot_server==NordelunaOnline.server; end
      def reset_cache; @snapshot=@snapshot_server=@health_server=nil; end
      def api(action,data={})
        NordelunaOnline.request(NordelunaOnline.server,data.merge('action'=>action,'account'=>Identity.ensure_registered))
      end
      def pending; $PokemonGlobal.nordeluna_shop_pending; end
      def save!
        Gifts.save!
        saved=Marshal.load(File.binread(SaveData::FILE_PATH))[:global_metadata]
        raise Error,'A compra nao foi confirmada no save.' unless saved.nordeluna_shop_pending==pending
      end
      def sync
        if @health_server!=NordelunaOnline.server || NordelunaOnline.now>=(@health_until || 0)
          health=NordelunaOnline.test_connection(false)
          raise VersionMismatch,'Luna Coins precisam do servidor revisao 9.' unless health['revision'].to_i>=9
          @health_server=NordelunaOnline.server;@health_until=NordelunaOnline.now+60
        end
        retry_reports
        @snapshot=api('economy_sync')
        CosmeticBadges.receive(@snapshot['equipped_badge']) if defined?(CosmeticBadges) && @snapshot.key?('equipped_badge')
        @snapshot_server=NordelunaOnline.server
        @snapshot
      end
      def report_battle(session,result)
        return unless [1,2,5].include?(result)
        report={'url'=>NordelunaOnline.server,'code'=>session.code,'token'=>session.ticket['token'],'result'=>result}
        reports=$PokemonGlobal.nordeluna_battle_reports || []
        $PokemonGlobal.nordeluna_battle_reports=(reports.reject { |r| r['code']==report['code'] }+[report]).last(10)
        Gifts.save!
        retry_reports
      rescue StandardError => error
        NordelunaOnline.record_online_error(error,'mission_battle_result')
      end
      def retry_reports
        rows=$PokemonGlobal.nordeluna_battle_reports || []
        rows.dup.each do |report|
          next unless report['url']==NordelunaOnline.server
          begin
            NordelunaOnline.request(report['url'],'action'=>'battle_result','code'=>report['code'],'token'=>report['token'],'result'=>report['result'])
          rescue Error => error
            raise unless error.message.match?(/dois turnos|Resultado ja registrado|interrompida|Sala nao encontrada|Sessao invalida/)
          end
          rows.delete(report)
          Gifts.save!
        end
      end
      def finish_purchase(claim,balance=nil)
        if balance.is_a?(Integer) && balance>=0
          @snapshot=(@snapshot || {}).merge('balance'=>balance)
          @snapshot_server=NordelunaOnline.server
        end
        if !claim
          $PokemonGlobal.nordeluna_shop_pending=nil
          save!
          return pbMessage(_INTL('O servidor confirmou que esta compra nao foi cobrada.'))
        end
        receipt=Gifts.receipts.find { |row| row['id']==claim['id'] && row['url']==NordelunaOnline.server }
        if receipt
          Gifts.acknowledge(receipt)
        else
          if Gifts.pending
            raise Error,'Recupere o presente pendente antes desta compra.' unless Gifts.pending['claim']['id']==claim['id']
          else
            Gifts.prepare(claim)
          end
        end
        $PokemonGlobal.nordeluna_shop_pending=nil
        save!
        Gifts.deliver unless receipt
        pbMessage(_INTL('Compra recebida e salva!'))
      end
      def recover_purchase
        raise Error,'Nenhuma compra pendente.' unless pending
        raise Error,'Volte ao servidor original da compra.' unless pending['url']==NordelunaOnline.server
        reply=api('economy_order','order'=>pending['id'])
        finish_purchase(reply['claim'],reply['balance'])
      end
      def buy(item)
        return recover_purchase if pending
        return pbMessage(_INTL('Este produto esta indisponivel no momento. Nenhuma moeda foi cobrada.')) if item['enabled']==false
        Gifts.validate_rewards(item['rewards'])
        if item['rewards'].any? { |row| row['kind']=='outfit' && Wardrobe.owned.include?(row['id']) }
          return pbMessage(_INTL('Voce ja possui esta roupa. Nenhuma moeda foi cobrada.'))
        end
        return unless ShopPreview.open(item,@snapshot['balance'])==:buy
        raise Error,'Recupere primeiro o presente pendente.' if Gifts.pending
        old=pending
        $PokemonGlobal.nordeluna_shop_pending={'id'=>Random.bytes(16).unpack1('H*'),'sku'=>item['id'],'url'=>NordelunaOnline.server}
        begin
          save!
        rescue StandardError
          $PokemonGlobal.nordeluna_shop_pending=old
          raise
        end
        reply=api('economy_buy','sku'=>item['id'],'order'=>pending['id'],'expected_price'=>item['price'])
        finish_purchase(reply['claim'],reply['balance'])
      end
      def missions
        sync
        rows=@snapshot['missions']
        n=OnlineUI.choose('Missoes diarias',rows.map { |r| "#{r['title']} #{r['progress']}/#{r['target']} / #{r['claimed'] ? 'Recebido' : "+#{r['coins']} LC"}" }+['Voltar'],rows.length,"Renovacao diaria UTC-3 / #{@snapshot['balance']} Luna Coins")
        return unless n>=0 && n<rows.length
        @snapshot=api('economy_claim','mission'=>rows[n]['id'])
        pbMessage(_INTL('Recompensa conferida. Saldo: {1} Luna Coins.',@snapshot['balance']))
      end
      def shop
        ShopFavorites.browse
      end
      def community
        sync
        data=@snapshot['community']
        return pbMessage(_INTL('Nao ha desafio comunitario ativo no momento.')) if data['enabled']==false
        n=OnlineUI.choose(data['title'],["Progresso: #{data['progress']}/#{data['target']}",
          data['claimed'] ? 'Recompensa recebida' : "Resgatar #{data['coins']} Luna Coins",'Voltar'],2,
          data['contributed'] ? 'Sua participacao foi registrada' : 'Conclua uma batalha para participar')
        return unless n==1
        @snapshot=api('economy_claim','mission'=>data['id'])
        pbMessage(_INTL('Recompensa comunitaria conferida! Saldo: {1} Luna Coins.',@snapshot['balance']))
      end
      def open
        sync
        loop do
          n=OnlineUI.choose('Central Luna Coins',['Missoes diarias','Loja lunar','Desafio comunitario','Extrato',pending ? 'Recuperar compra pendente' : 'Atualizar saldo','Voltar'],5,"Saldo: #{@snapshot && @snapshot['balance'] || '--'} Luna Coins")
          case n
          when 0 then missions
          when 1 then shop
          when 2 then community
          when 3
            data=api('economy_ledger')
            OnlineUI.choose('Extrato',data['entries'].map { |row| "#{row['amount']>0 ? '+' : ''}#{row['amount']} LC / #{row['event']}" }+['Voltar'],data['entries'].length)
          when 4 then pending ? recover_purchase : sync
          else return
          end
        end
      rescue Error => error
        pbMessage(_INTL('Luna Coins: {1}',error.message))
      rescue StandardError => error
        NordelunaOnline.record_online_error(error,'luna_economy')
        pbMessage(_INTL('Nao foi possivel concluir. Compras cobradas continuam recuperaveis.'))
      end
    end
  end
  module LunaBattleProgress
    def start_battle(session,room)
      result=super
      LunaEconomy.report_battle(session,result)
      result
    end
  end
  singleton_class.prepend(LunaBattleProgress)
end
