/* Relive Malta: ten calm, flat illustrations (no text, no logos, no people), drawn for the memory cards.
   To use a real photo instead, put an image in html/images and change the entry to '<img src="images/NAME.jpg" alt="">'. */
(function (w) {
  'use strict';
  var H = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220" focusable="false">';
  var E = '</svg>';
  var STAR = 'M0-22L6-8L21-7L10 3L14 18L0 10L-14 18L-10 3L-21-7L-6-8Z';
  w.MemArt = {
    festa: H + '<rect width="320" height="220" fill="#34506F"/>' +
      '<g stroke-width="4" stroke-linecap="round" fill="none"><g stroke="#F4C542"><path d="M70 52v-22M70 52v22M48 52h-22M92 52h22M54 36l-15-15M86 36l15-15M54 68l-15 15M86 68l15 15"/></g>' +
      '<g stroke="#F08A7E"><path d="M255 40v-18M255 40v18M237 40h-18M273 40h18M243 28l-12-12M267 28l12-12M243 52l-12 12M267 52l12 12"/></g></g>' +
      '<rect x="100" y="112" width="120" height="82" fill="#EBD9A8"/>' +
      '<path d="M122 112A38 38 0 0 1 198 112Z" fill="#C9B07A"/><rect x="156" y="68" width="8" height="12" fill="#C9B07A"/><path d="M152 68L160 56L168 68Z" fill="#B9A06A"/>' +
      '<rect x="92" y="100" width="26" height="94" fill="#E3CF9C"/><rect x="202" y="100" width="26" height="94" fill="#E3CF9C"/>' +
      '<path d="M90 100L105 78L120 100Z" fill="#B9A06A"/><path d="M200 100L215 78L230 100Z" fill="#B9A06A"/>' +
      '<path d="M146 194V166a14 14 0 0 1 28 0V194Z" fill="#6E4F34"/>' +
      '<rect x="0" y="194" width="320" height="26" fill="#5B7B58"/>' +
      '<path d="M0 90L320 90" stroke="#FFFFFF" stroke-width="2"/>' +
      '<g><polygon points="20,90 36,90 28,106" fill="#D9534F"/><polygon points="60,90 76,90 68,106" fill="#F4C542"/><polygon points="240,90 256,90 248,106" fill="#6FAF7B"/><polygon points="284,90 300,90 292,106" fill="#D9534F"/></g>' + E,

    luzzu: H + '<rect width="320" height="220" fill="#CFE6F3"/><circle cx="252" cy="52" r="26" fill="#F8D66A"/>' +
      '<rect y="128" width="320" height="92" fill="#7DB7D6"/>' +
      '<path d="M0 150Q20 142 40 150T80 150T120 150T160 150T200 150T240 150T280 150T320 150" fill="none" stroke="#A9D2E6" stroke-width="3"/>' +
      '<path d="M0 196Q20 188 40 196T80 196T120 196T160 196T200 196T240 196T280 196T320 196" fill="none" stroke="#6AA7C9" stroke-width="3"/>' +
      '<path d="M54 118L252 118Q262 100 280 82L286 86Q276 106 270 118L262 140Q248 170 206 172L112 172Q70 170 54 118Z" fill="#2F80B7"/>' +
      '<path d="M54 118L270 118L264 134L60 134Z" fill="#F4C542"/>' +
      '<path d="M262 118Q272 100 280 82L286 86Q277 104 270 118Z" fill="#D9534F"/>' +
      '<circle cx="246" cy="152" r="10" fill="#FFFFFF"/><circle cx="249" cy="152" r="5" fill="#34506F"/>' +
      '<rect x="120" y="86" width="52" height="32" rx="4" fill="#F7F2E4"/><rect x="132" y="94" width="12" height="12" fill="#7DB7D6"/><rect x="150" y="94" width="12" height="12" fill="#7DB7D6"/>' +
      '<path d="M200 118V70" stroke="#34506F" stroke-width="4"/><path d="M200 70L226 80L200 90Z" fill="#D9534F"/>' + E,

    ferry: H + '<rect width="320" height="220" fill="#D6EAF5"/><circle cx="70" cy="48" r="22" fill="#F8D66A"/>' +
      '<path d="M170 140Q205 96 240 104Q262 78 290 98Q310 100 320 120V140Z" fill="#B8C98A"/><path d="M236 104h40v-14h-6v-8h-6v8h-6v-8h-6v8h-6v-8h-6v8h-4Z" fill="#E3CF9C"/>' +
      '<rect y="138" width="320" height="82" fill="#6FAFD3"/>' +
      '<path d="M0 160Q20 152 40 160T80 160T120 160T160 160T200 160T240 160T280 160T320 160" fill="none" stroke="#9CCBE3" stroke-width="3"/>' +
      '<path d="M0 200Q20 192 40 200T80 200T120 200T160 200T200 200T240 200T280 200T320 200" fill="none" stroke="#5FA0C6" stroke-width="3"/>' +
      '<path d="M32 150L196 150L184 184L52 184Z" fill="#2F4F7F"/>' +
      '<rect x="52" y="116" width="124" height="34" rx="4" fill="#FFFFFF"/>' +
      '<g fill="#7DB7D6"><rect x="62" y="124" width="14" height="14"/><rect x="84" y="124" width="14" height="14"/><rect x="106" y="124" width="14" height="14"/><rect x="128" y="124" width="14" height="14"/><rect x="150" y="124" width="14" height="14"/></g>' +
      '<rect x="92" y="92" width="48" height="24" rx="3" fill="#F2F5F8"/><rect x="108" y="72" width="16" height="22" fill="#D9534F"/><rect x="108" y="78" width="16" height="5" fill="#FFFFFF"/>' + E,

    pastizzi: H + '<rect width="320" height="220" fill="#FBEBD2"/>' +
      '<ellipse cx="112" cy="158" rx="92" ry="26" fill="#FFFFFF" stroke="#D9C9A8" stroke-width="3"/>' +
      '<path d="M54 146Q86 108 118 146Q86 170 54 146Z" fill="#E8B05C"/><path d="M104 140Q136 102 168 140Q136 164 104 140Z" fill="#EBB868"/>' +
      '<path d="M64 146Q86 134 108 146M114 140Q136 128 158 140" fill="none" stroke="#C98B3A" stroke-width="3" stroke-linecap="round"/>' +
      '<ellipse cx="248" cy="176" rx="56" ry="12" fill="#FFFFFF" stroke="#D9C9A8" stroke-width="3"/>' +
      '<path d="M206 118h84v26a42 34 0 0 1-84 0Z" fill="#FFFFFF" stroke="#C9B28A" stroke-width="3"/><path d="M212 124h72v8h-72Z" fill="#A9552B"/>' +
      '<path d="M290 126a18 16 0 0 1 0 32" fill="none" stroke="#C9B28A" stroke-width="6"/>' +
      '<path d="M232 108Q224 94 232 82Q240 70 232 58M258 108Q250 94 258 82Q266 70 258 58" fill="none" stroke="#C7B8A0" stroke-width="4" stroke-linecap="round"/>' + E,

    harbour: H + '<rect width="320" height="220" fill="#CFE6F3"/><circle cx="262" cy="40" r="20" fill="#F8D66A"/>' +
      '<g fill="#E8D6A2"><rect x="30" y="72" width="40" height="46"/><rect x="76" y="86" width="32" height="32"/><rect x="190" y="78" width="34" height="40"/><rect x="230" y="92" width="44" height="26"/></g>' +
      '<path d="M114 118V92A30 30 0 0 1 174 92V118Z" fill="#D9C08A"/><rect x="141" y="52" width="6" height="12" fill="#D9C08A"/><path d="M138 52L144 42L150 52Z" fill="#B9A06A"/>' +
      '<g fill="#BFA36A"><rect x="30" y="64" width="10" height="8"/><rect x="190" y="70" width="10" height="8"/></g>' +
      '<rect y="118" width="320" height="40" fill="#C9B07A"/><g fill="#B9A06A"><rect x="6" y="110" width="22" height="10"/><rect x="48" y="110" width="22" height="10"/><rect x="90" y="110" width="22" height="10"/><rect x="132" y="110" width="22" height="10"/><rect x="174" y="110" width="22" height="10"/><rect x="216" y="110" width="22" height="10"/><rect x="258" y="110" width="22" height="10"/></g>' +
      '<rect y="158" width="320" height="62" fill="#6FAFD3"/>' +
      '<path d="M0 178Q20 170 40 178T80 178T120 178T160 178T200 178T240 178T280 178T320 178" fill="none" stroke="#9CCBE3" stroke-width="3"/>' +
      '<path d="M120 192L200 192L188 208L132 208Z" fill="#D9534F"/><path d="M160 192V160L186 192Z" fill="#FFFFFF"/>' + E,

    baker: H + '<rect width="320" height="220" fill="#F8E6C8"/>' +
      '<path d="M96 150V100a64 64 0 0 1 128 0V150Z" fill="#FCEFD4"/><circle cx="160" cy="88" r="26" fill="#F8D66A"/>' +
      '<path d="M160 52v-14M160 138v-14M124 88h-14M210 88h-14M134 62l-10-10M186 62l10-10" stroke="#F0B84A" stroke-width="4" stroke-linecap="round"/>' +
      '<path d="M58 146H262L246 202H74Z" fill="#B97A45"/><path d="M64 164H256M68 182H252" stroke="#9A6234" stroke-width="3"/><path d="M110 146L102 202M160 146V202M210 146L218 202" stroke="#9A6234" stroke-width="3"/>' +
      '<ellipse cx="108" cy="140" rx="40" ry="24" fill="#DDA054"/><path d="M88 128l10 18M108 124l8 22M128 130l6 16" stroke="#B9782E" stroke-width="3" stroke-linecap="round"/>' +
      '<ellipse cx="190" cy="138" rx="34" ry="24" fill="#E5AB60"/><path d="M174 126l8 18M194 124l6 22" stroke="#B9782E" stroke-width="3" stroke-linecap="round"/>' +
      '<circle cx="240" cy="146" r="22" fill="#D99A4E"/><circle cx="240" cy="146" r="8" fill="#F8E6C8"/>' + E,

    crib: H + '<rect width="320" height="220" fill="#27405E"/>' +
      '<g transform="translate(160 48)"><path d="' + STAR + '" fill="#F8D66A"/></g><path d="M160 76V104" stroke="#F8D66A" stroke-width="3" stroke-linecap="round" opacity="0.7"/>' +
      '<g fill="#F4F0D8"><circle cx="40" cy="40" r="2.5"/><circle cx="280" cy="30" r="2.5"/><circle cx="64" cy="96" r="2"/><circle cx="262" cy="86" r="2"/><circle cx="300" cy="120" r="2"/><circle cx="22" cy="130" r="2"/></g>' +
      '<path d="M84 128L160 82L236 128Z" fill="#8B5E3C"/><rect x="96" y="128" width="8" height="60" fill="#6E4A2E"/><rect x="216" y="128" width="8" height="60" fill="#6E4A2E"/>' +
      '<rect x="0" y="186" width="320" height="34" fill="#5E7E5A"/><path d="M104 188Q160 172 216 188Z" fill="#E3C46E"/>' +
      '<circle cx="160" cy="166" r="24" fill="#F8D66A" opacity="0.35"/><path d="M140 176h40l-6 14h-28Z" fill="#B97A45"/><ellipse cx="160" cy="172" rx="16" ry="5" fill="#F7F2E4"/>' +
      '<rect x="256" y="156" width="14" height="34" rx="2" fill="#F7F2E4"/><path d="M263 156Q256 146 263 136Q270 146 263 156Z" fill="#F4A53A"/>' +
      '<rect x="50" y="160" width="14" height="30" rx="2" fill="#F7F2E4"/><path d="M57 160Q50 150 57 140Q64 150 57 160Z" fill="#F4A53A"/>' + E,

    carnival: H + '<rect width="320" height="220" fill="#FDF0D8"/>' +
      '<g transform="rotate(-24 120 70)"><ellipse cx="120" cy="64" rx="12" ry="40" fill="#F08A7E"/></g><g transform="rotate(-4 160 60)"><ellipse cx="160" cy="58" rx="12" ry="44" fill="#F4C542"/></g><g transform="rotate(20 200 70)"><ellipse cx="200" cy="64" rx="12" ry="40" fill="#5FB3A8"/></g>' +
      '<path d="M70 118Q160 78 250 118Q262 150 224 160Q196 160 182 140Q160 128 138 140Q124 160 96 160Q58 150 70 118Z" fill="#8E5CC2"/>' +
      '<ellipse cx="118" cy="132" rx="18" ry="11" fill="#FDF0D8"/><ellipse cx="202" cy="132" rx="18" ry="11" fill="#FDF0D8"/>' +
      '<path d="M84 122Q160 92 236 122" fill="none" stroke="#F4C542" stroke-width="4" stroke-linecap="round"/>' +
      '<circle cx="160" cy="114" r="6" fill="#F4C542"/>' +
      '<path d="M20 36Q50 60 20 84T20 132" fill="none" stroke="#5FB3A8" stroke-width="5" stroke-linecap="round"/><path d="M300 36Q270 60 300 84T300 132" fill="none" stroke="#F08A7E" stroke-width="5" stroke-linecap="round"/>' +
      '<g><rect x="40" y="170" width="10" height="10" fill="#F08A7E" transform="rotate(20 45 175)"/><rect x="92" y="190" width="10" height="10" fill="#5FB3A8" transform="rotate(-20 97 195)"/><rect x="226" y="180" width="10" height="10" fill="#F4C542" transform="rotate(30 231 185)"/><circle cx="270" cy="196" r="6" fill="#8E5CC2"/><circle cx="150" cy="198" r="5" fill="#F08A7E"/><circle cx="60" cy="150" r="5" fill="#F4C542"/></g>' + E,

    beach: H + '<rect width="320" height="220" fill="#CFE6F3"/><circle cx="262" cy="48" r="26" fill="#F8D66A"/>' +
      '<rect y="96" width="320" height="52" fill="#6FAFD3"/><path d="M0 116Q20 108 40 116T80 116T120 116T160 116T200 116T240 116T280 116T320 116" fill="none" stroke="#9CCBE3" stroke-width="3"/>' +
      '<path d="M0 148Q80 134 160 146T320 142V220H0Z" fill="#F2E2BC"/>' +
      '<path d="M100 164V86" stroke="#8B5E3C" stroke-width="5" stroke-linecap="round"/>' +
      '<path d="M44 96A56 44 0 0 1 156 96Z" fill="#D9534F"/><path d="M72 96A28 44 0 0 1 100 52L100 96Z" fill="#FFFFFF"/><path d="M128 96A28 44 0 0 0 100 52L100 96Z" fill="#FFFFFF"/>' +
      '<path d="M44 96Q58 104 72 96Q86 104 100 96Q114 104 128 96Q142 104 156 96" fill="none" stroke="#B93C38" stroke-width="3"/>' +
      '<rect x="190" y="170" width="92" height="34" rx="3" fill="#2F80B7"/><path d="M190 180H282M190 192H282" stroke="#FFFFFF" stroke-width="5"/>' +
      '<path d="M212 154h26l-4 14h-18Z" fill="#E5A23C"/><path d="M214 154q11-12 22 0" fill="none" stroke="#B97A45" stroke-width="3"/>' + E,

    balconies: H + '<rect width="320" height="220" fill="#CFE6F3"/>' +
      '<rect x="0" y="0" width="320" height="220" fill="#EBD9A8"/><path d="M0 190H320V220H0Z" fill="#CBB887"/>' +
      '<g><rect x="22" y="52" width="86" height="64" rx="3" fill="#3E8E6E"/><rect x="22" y="44" width="86" height="10" fill="#2F6F55"/><g fill="#CFE8DC"><rect x="30" y="64" width="20" height="44"/><rect x="58" y="64" width="20" height="44"/><rect x="86" y="64" width="14" height="44"/></g></g>' +
      '<g><rect x="118" y="86" width="86" height="64" rx="3" fill="#2F80B7"/><rect x="118" y="78" width="86" height="10" fill="#235F88"/><g fill="#D2E6F3"><rect x="126" y="98" width="20" height="44"/><rect x="154" y="98" width="20" height="44"/><rect x="182" y="98" width="14" height="44"/></g></g>' +
      '<g><rect x="214" y="44" width="86" height="64" rx="3" fill="#C75B4A"/><rect x="214" y="36" width="86" height="10" fill="#9C4538"/><g fill="#F2D4CD"><rect x="222" y="56" width="20" height="44"/><rect x="250" y="56" width="20" height="44"/><rect x="278" y="56" width="14" height="44"/></g></g>' +
      '<g fill="#6E4F34"><path d="M30 190V150a14 14 0 0 1 28 0V190Z"/><path d="M142 190V156a14 14 0 0 1 28 0V190Z"/><path d="M246 190V152a14 14 0 0 1 28 0V190Z"/></g>' +
      '<g><rect x="96" y="176" width="14" height="14" fill="#B97A45"/><circle cx="103" cy="170" r="9" fill="#6FAF7B"/><rect x="204" y="176" width="14" height="14" fill="#B97A45"/><circle cx="211" cy="170" r="9" fill="#6FAF7B"/></g>' + E
  };
  w.MemArtKeys = ['festa', 'luzzu', 'ferry', 'pastizzi', 'harbour', 'baker', 'crib', 'carnival', 'beach', 'balconies'];
})(window);
