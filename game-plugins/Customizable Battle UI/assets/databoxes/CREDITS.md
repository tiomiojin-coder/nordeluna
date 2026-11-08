# Battle boxes — sources and scope

* Existing red/blue theme graphics: Toxillian, Customizable Battle UI.
  https://eeveeexpo.com/resources/1312/
* Emerald box, HP/EXP bars and number graphics: Voltseon's Emerald UI Pack 1.2;
  battle UI credited to Pokemon Splice Team on the resource page.
  https://eeveeexpo.com/resources/965/
* Sword/Shield-inspired (Gen 4 adaptation) box, bars and numbers: BiggusWeeabus.
  This is an adaptation, not an exact rip of Sword/Shield's Switch interface.
  https://eeveeexpo.com/resources/860/
* Original Pokemon graphics belong to their respective creators / Game Freak.

Nordeluna's selector/renderer integration is in 004_DataBoxStyles.rb. Battle
Databox Styles by BoydALoyd was evaluated, but its source was not bundled or
modified here: the installed UI already owns the same methods. This integration
implements one shared preference for both sides without installing two conflicting overrides.

Only battle box assets from Emerald and SwSh were selected. Bag, party, Pokedex,
battlebacks, gameplay scripts and move animations from these packs were not
installed. Existing Nordeluna ability-bar fixes and battle menus are preserved.
