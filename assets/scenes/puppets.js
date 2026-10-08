/* Puppets: the minimal flat drawings of the scene decks (kids' site, Baloney Detector, the guide), drawn in code.
   Puppets.actor(who) → SVG markup for a character (all moods are in the markup; CSS shows the one in .f-<mood>);
   Puppets.prop(what) → SVG markup for a thing; Puppets.bg(name) → SVG markup for a backdrop.
   The names are listed in assets/scenes/vocab.json, which tools/scenes/scenes.py checks decks against. */
(function () {
  "use strict";
  var INK = "#1E2A3B";

  // ---- faces: every mood is drawn; the stage shows one (.f-happy, .f-sad, …). (cx, cy) is the middle of the eyes.
  function face(cx, cy, k) {
    k = k || 1;
    var e = function (x) { return '<circle cx="' + x + '" cy="0" r="2.6" fill="' + INK + '"/><circle cx="' + (x + .9) + '" cy="-1" r=".9" fill="#fff"/>'; };
    return '<g transform="translate(' + cx + ' ' + cy + ') scale(' + k + ')" class="face">' +
      '<g class="eyes">' + e(-8) + e(8) + '</g>' +
      '<g class="eyes-sly"><path d="M-12 -2 L-4 -2 M4 -2 L12 -2" stroke="' + INK + '" stroke-width="2.4" stroke-linecap="round"/>' + '<circle cx="-8" cy="1" r="2.2" fill="' + INK + '"/><circle cx="8" cy="1" r="2.2" fill="' + INK + '"/></g>' +
      '<g class="eyes-wide"><circle cx="-8" cy="0" r="4" fill="#fff" stroke="' + INK + '" stroke-width="1.4"/><circle cx="8" cy="0" r="4" fill="#fff" stroke="' + INK + '" stroke-width="1.4"/><circle cx="-8" cy="0" r="1.8" fill="' + INK + '"/><circle cx="8" cy="0" r="1.8" fill="' + INK + '"/></g>' +
      '<g class="brows"><path class="b-sad" d="M-13 -8 L-4 -11 M13 -8 L4 -11" stroke="' + INK + '" stroke-width="2" stroke-linecap="round"/>' +
      '<path class="b-think" d="M-13 -9 L-4 -9 M4 -12 Q9 -15 13 -11" stroke="' + INK + '" stroke-width="2" stroke-linecap="round" fill="none"/>' +
      '<path class="b-wide" d="M-13 -11 Q-8 -14 -3 -11 M3 -11 Q8 -14 13 -11" stroke="' + INK + '" stroke-width="2" stroke-linecap="round" fill="none"/></g>' +
      '<path class="m m-happy" d="M-7 8 Q0 15 7 8" stroke="' + INK + '" stroke-width="2.4" fill="none" stroke-linecap="round"/>' +
      '<path class="m m-sad" d="M-6 13 Q0 7 6 13" stroke="' + INK + '" stroke-width="2.4" fill="none" stroke-linecap="round"/>' +
      '<ellipse class="m m-surprised" cx="0" cy="11" rx="3.4" ry="4.6" fill="#7A2E3A"/>' +
      '<path class="m m-thinking" d="M-5 11 Q0 9 6 12" stroke="' + INK + '" stroke-width="2.4" fill="none" stroke-linecap="round"/>' +
      '<path class="m m-sly" d="M-7 10 Q0 14 8 6" stroke="' + INK + '" stroke-width="2.4" fill="none" stroke-linecap="round"/>' +
      '<ellipse class="m m-talk" cx="0" cy="10" rx="4" ry="3" fill="#7A2E3A"/>' +
      '<circle cx="-13" cy="8" r="3" fill="#F37A8B" opacity=".45"/><circle cx="13" cy="8" r="3" fill="#F37A8B" opacity=".45"/></g>';
  }

  // ---- people (viewBox 0 0 100 160, feet at y = 156)
  var SKIN = "#E8B48A", DARK = "#1D1A22";
  function person(c) {
    var s = '<svg viewBox="0 0 100 160" class="pp">';
    s += '<ellipse cx="50" cy="156" rx="26" ry="4" fill="rgba(0,0,0,.14)"/>';
    s += c.back || "";
    s += '<g class="legs"><rect x="36" y="108" width="11" height="42" rx="5" fill="' + c.pants + '"/><rect x="53" y="108" width="11" height="42" rx="5" fill="' + c.pants + '"/>' +
      '<ellipse cx="40" cy="152" rx="9" ry="5" fill="' + c.shoes + '"/><ellipse cx="60" cy="152" rx="9" ry="5" fill="' + c.shoes + '"/></g>';
    s += '<g class="arm arm-l"><path d="M31 74 L19 104" stroke="' + (c.sleeve || c.shirt) + '" stroke-width="10" stroke-linecap="round"/><circle cx="18.5" cy="106" r="5" fill="' + SKIN + '"/></g>';
    s += '<rect x="28" y="64" width="44" height="52" rx="14" fill="' + c.shirt + '"/>';
    s += c.torso || "";
    s += '<g class="arm arm-r"><path d="M69 74 L81 104" stroke="' + (c.sleeve || c.shirt) + '" stroke-width="10" stroke-linecap="round"/><circle cx="81.5" cy="106" r="5" fill="' + SKIN + '"/></g>';
    s += '<g class="head"><rect x="44" y="58" width="12" height="10" fill="' + (c.skin || SKIN) + '"/>' + (c.behind || "") +
      '<circle cx="50" cy="40" r="22" fill="' + (c.skin || SKIN) + '"/><circle cx="28" cy="42" r="4" fill="' + (c.skin || SKIN) + '"/><circle cx="72" cy="42" r="4" fill="' + (c.skin || SKIN) + '"/>' +
      (c.hair || "") + face(50, 42) + (c.glasses || "") + '</g></svg>';
    return s;
  }
  var glass = function (col) { return '<g fill="none" stroke="' + col + '" stroke-width="2.4"><circle cx="42" cy="42" r="7.5"/><circle cx="58" cy="42" r="7.5"/><path d="M49.5 42 h1"/></g>'; };
  var WHO = {
    ava: function () { return person({ shirt: "#FFFFFF", sleeve: "#FFFFFF", pants: "#4F7FB5", shoes: "#D93A3A",
      behind: '<path d="M22 36 Q22 14 50 14 Q78 14 78 36 L80 66 Q50 74 20 66Z" fill="' + DARK + '"/>',
      torso: '<path d="M30 80 Q30 76 34 76 L66 76 Q70 76 70 80 L72 116 Q50 122 28 116Z" fill="#2FA6A0"/><path d="M38 66 L40 78 M62 66 L60 78" stroke="#2FA6A0" stroke-width="4"/><rect x="40" y="94" width="20" height="12" rx="3" fill="#25908A"/>',
      hair: '<path d="M27 40 Q30 14 50 14 Q70 14 73 40 Q60 24 50 26 Q38 24 27 40Z" fill="' + DARK + '"/><path d="M28 31 Q50 8 72 31" stroke="#F2B84B" stroke-width="5" fill="none" stroke-linecap="round"/>',
      glasses: glass("#D93A3A") }); },
    nima: function () { return person({ shirt: "#FF9A3C", sleeve: "#FF9A3C", pants: "#5C8F4E", shoes: "#3E67B8",
      torso: '<g stroke="#fff" stroke-width="4"><path d="M29 76 H71 M29 88 H71 M29 100 H71"/></g>',
      hair: '<g fill="' + DARK + '"><circle cx="31" cy="26" r="10"/><circle cx="43" cy="18" r="11"/><circle cx="57" cy="18" r="11"/><circle cx="69" cy="26" r="10"/><circle cx="27" cy="38" r="8"/><circle cx="73" cy="38" r="8"/></g>' }); },
    kian: function () { return person({ shirt: "#2F5FD0", sleeve: "#2F5FD0", pants: "#33415C", shoes: "#EDEDED",
      back: '<rect x="62" y="72" width="22" height="36" rx="8" fill="#A5793A"/>',
      torso: '<path d="M44 66 Q50 74 56 66" stroke="#fff" stroke-width="2.4" fill="none"/><rect x="40" y="94" width="20" height="14" rx="5" fill="#2650B5"/><path d="M36 64 L38 80 M64 64 L62 80" stroke="#A5793A" stroke-width="4"/>',
      hair: '<path d="M28 38 L31 18 L40 27 L46 11 L54 25 L62 13 L68 26 L74 19 L72 38 Q50 26 28 38Z" fill="' + DARK + '"/>' }); },
    grandma: function () { return person({ shirt: "#7B3F6B", sleeve: "#7B3F6B", pants: "#6B4A74", shoes: "#8A5A3C",
      torso: '<path d="M30 70 L26 118 Q50 126 74 118 L70 70Z" fill="#7B3F6B"/><g fill="#F3B6C8"><circle cx="38" cy="86" r="3"/><circle cx="58" cy="82" r="3"/><circle cx="46" cy="102" r="3"/><circle cx="64" cy="100" r="3"/></g><path d="M50 70 V118" stroke="#5E2F52" stroke-width="2"/>',
      behind: '<ellipse cx="50" cy="42" rx="26" ry="26" fill="#D7D9E0"/>',
      hair: '<path d="M25 46 Q24 12 50 12 Q76 12 75 46 Q72 28 50 27 Q28 28 25 46Z" fill="#E88FA6"/><g fill="#fff" opacity=".7"><circle cx="34" cy="22" r="2.4"/><circle cx="48" cy="17" r="2.4"/><circle cx="62" cy="21" r="2.4"/><circle cx="70" cy="31" r="2.4"/></g>',
      glasses: glass("#6B4A2B") }); },
    person: function () { return person({ shirt: "#7B8BA6", sleeve: "#7B8BA6", pants: "#46526B", shoes: "#2A2F3A",
      hair: '<path d="M29 38 Q50 6 71 38 Q50 26 29 38Z" fill="#4A3B33"/>' }); }
  };
  // ---- animals and Hudhud (viewBox 0 0 100 110 / 120)
  function goat(body, patch, collar, scarf, big) {
    var horn = big ? 'M40 26 Q30 6 40 4 M60 26 Q70 6 60 4' : 'M42 28 Q38 16 44 14 M58 28 Q62 16 56 14';
    return '<svg viewBox="0 0 100 120" class="pp"><ellipse cx="50" cy="116" rx="30" ry="4" fill="rgba(0,0,0,.14)"/>' +
      '<g fill="' + body + '"><rect x="30" y="86" width="9" height="28" rx="4"/><rect x="61" y="86" width="9" height="28" rx="4"/><ellipse cx="50" cy="82" rx="26" ry="24"/></g>' +
      (patch ? '<ellipse cx="38" cy="82" rx="9" ry="12" fill="' + patch + '"/><ellipse cx="62" cy="90" rx="7" ry="8" fill="' + patch + '"/>' : '') +
      '<g fill="#5A3A22"><rect x="30" y="108" width="9" height="6" rx="2"/><rect x="61" y="108" width="9" height="6" rx="2"/></g>' +
      '<path d="' + horn + '" stroke="#7A6A5A" stroke-width="5" stroke-linecap="round" fill="none"/>' +
      '<ellipse cx="28" cy="44" rx="11" ry="6" transform="rotate(-20 28 44)" fill="' + body + '"/><ellipse cx="72" cy="44" rx="11" ry="6" transform="rotate(20 72 44)" fill="' + body + '"/>' +
      '<ellipse cx="29" cy="44" rx="6" ry="3" transform="rotate(-20 29 44)" fill="#F2B6B0"/><ellipse cx="71" cy="44" rx="6" ry="3" transform="rotate(20 71 44)" fill="#F2B6B0"/>' +
      '<circle cx="50" cy="44" r="19" fill="' + body + '"/><ellipse cx="50" cy="55" rx="9" ry="7" fill="#F6E3D3"/><circle cx="46" cy="53" r="1.2" fill="#8A5A4A"/><circle cx="54" cy="53" r="1.2" fill="#8A5A4A"/>' +
      (scarf ? '<path d="M28 48 Q50 70 72 48 L66 40 Q50 52 34 40Z" fill="' + scarf + '"/>' : '<rect x="36" y="62" width="28" height="6" rx="3" fill="' + collar + '"/><circle cx="50" cy="71" r="4" fill="#E8B83A"/>') +
      '<g class="head">' + face(50, 40, .8) + '</g></svg>';
  }
  var ANIMALS = {
    mother: function () { return goat("#FFFFFF", "#C98B4E", "#3E67B8", "#3AA0D8", true); },
    shangul: function () { return goat("#FFFFFF", "", "#D93A3A", ""); },
    mangul: function () { return goat("#D9A765", "", "#2FA66A", ""); },
    grape: function () { return goat("#F6E9C8", "", "#8B5CF6", ""); },
    wolf: function () { return '<svg viewBox="0 0 100 150" class="pp"><ellipse cx="50" cy="146" rx="28" ry="4" fill="rgba(0,0,0,.14)"/>' +
      '<path d="M72 100 Q96 96 92 124 Q88 108 70 112Z" fill="#6D7585"/>' +
      '<rect x="36" y="112" width="11" height="32" rx="5" fill="#6D7585"/><rect x="53" y="112" width="11" height="32" rx="5" fill="#6D7585"/>' +
      '<g class="arm arm-l"><path d="M32 78 L20 104" stroke="#6D7585" stroke-width="11" stroke-linecap="round"/></g>' +
      '<ellipse cx="50" cy="96" rx="24" ry="30" fill="#7D8697"/><ellipse cx="50" cy="100" rx="13" ry="20" fill="#C9CED8"/>' +
      '<g class="arm arm-r"><path d="M68 78 L80 104" stroke="#6D7585" stroke-width="11" stroke-linecap="round"/></g>' +
      '<g class="head"><path d="M28 30 L30 4 L44 22Z M72 30 L70 4 L56 22Z" fill="#6D7585"/><path d="M31 25 L32 11 L40 22Z M69 25 L68 11 L60 22Z" fill="#E7A9B0"/>' +
      '<circle cx="50" cy="42" r="22" fill="#7D8697"/><ellipse cx="50" cy="55" rx="14" ry="10" fill="#C9CED8"/><ellipse cx="50" cy="49" rx="6" ry="4.4" fill="#2B2F3A"/>' + face(50, 38, .95) + '</g></svg>'; },
    dog: function () { return '<svg viewBox="0 0 100 150" class="pp"><ellipse cx="50" cy="146" rx="28" ry="4" fill="rgba(0,0,0,.14)"/>' +
      '<rect x="37" y="114" width="10" height="30" rx="5" fill="#8A5A3C"/><rect x="53" y="114" width="10" height="30" rx="5" fill="#8A5A3C"/>' +
      '<g class="arm arm-l"><path d="M33 80 L20 106" stroke="#D9A629" stroke-width="10" stroke-linecap="round"/><circle cx="19" cy="108" r="5" fill="#8A5A3C"/></g>' +
      '<path d="M30 70 L26 122 Q50 130 74 122 L70 70Z" fill="#D9A629"/><path d="M50 70 V124" stroke="#B88A1C" stroke-width="2"/><rect x="30" y="98" width="40" height="5" fill="#B88A1C"/><path d="M42 68 L50 82 L58 68Z" fill="#fff"/>' +
      '<g class="arm arm-r"><path d="M67 80 L80 106" stroke="#D9A629" stroke-width="10" stroke-linecap="round"/><circle cx="81" cy="108" r="5" fill="#8A5A3C"/></g>' +
      '<g class="head"><ellipse cx="27" cy="42" rx="9" ry="17" transform="rotate(10 27 42)" fill="#6B3F26"/><ellipse cx="73" cy="42" rx="9" ry="17" transform="rotate(-10 73 42)" fill="#6B3F26"/>' +
      '<circle cx="50" cy="42" r="21" fill="#F4E4CB"/><path d="M40 20 Q50 30 60 20 Q50 14 40 20Z" fill="#6B3F26"/><ellipse cx="50" cy="52" rx="11" ry="8" fill="#fff"/><ellipse cx="50" cy="49" rx="5" ry="3.6" fill="#2B2F3A"/>' + face(50, 38, .9) +
      '<path d="M30 24 Q50 -2 70 24 L66 28 Q50 20 34 28Z" fill="#B58A3C"/><path d="M50 8 Q56 0 62 8Z" fill="#B58A3C"/><path d="M34 26 Q50 32 66 26" stroke="#8A6525" stroke-width="3" fill="none"/></g></svg>'; },
    hudhud: function () { return '<svg viewBox="0 0 100 110" class="pp"><ellipse cx="50" cy="106" rx="20" ry="3.5" fill="rgba(0,0,0,.14)"/>' +
      '<path d="M44 92 L40 104 M56 92 L60 104" stroke="#6B5A4A" stroke-width="3" stroke-linecap="round"/>' +
      '<g class="wing wing-l"><path d="M28 56 Q8 64 12 92 Q30 90 38 70Z" fill="#2B2F3A"/><path d="M16 74 Q24 72 32 74 M15 82 Q24 80 33 82" stroke="#fff" stroke-width="3" fill="none"/></g>' +
      '<ellipse cx="50" cy="68" rx="24" ry="28" fill="#F2A54A"/><ellipse cx="50" cy="74" rx="14" ry="20" fill="#F8D9A0"/>' +
      '<g class="wing wing-r"><path d="M72 56 Q92 64 88 92 Q70 90 62 70Z" fill="#2B2F3A"/><path d="M84 74 Q76 72 68 74 M85 82 Q76 80 67 82" stroke="#fff" stroke-width="3" fill="none"/></g>' +
      '<g class="head"><g class="crest"><path d="M50 30 L30 6 M50 30 L40 2 M50 30 L50 0 M50 30 L60 2 M50 30 L70 6" stroke="#F08A24" stroke-width="7" stroke-linecap="round"/><g fill="#2B2F3A"><circle cx="30" cy="6" r="3.6"/><circle cx="40" cy="2" r="3.6"/><circle cx="50" cy="0" r="3.6"/><circle cx="60" cy="2" r="3.6"/><circle cx="70" cy="6" r="3.6"/></g></g>' +
      '<circle cx="50" cy="42" r="19" fill="#F6B461"/><path d="M60 46 Q86 50 98 66 Q80 58 60 54Z" fill="#5A3A1E"/>' + face(46, 40, .72) + '</g></svg>'; }
  };
  var WHOS = {}; Object.keys(WHO).forEach(function (k) { WHOS[k] = WHO[k]; }); Object.keys(ANIMALS).forEach(function (k) { WHOS[k] = ANIMALS[k]; });

  // ---- props (viewBox 0 0 100 100 unless noted)
  var S = 'stroke="' + INK + '" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"';
  var PROPS = {
    cookie: '<circle cx="50" cy="50" r="30" fill="#D9A15E" ' + S + '/><g fill="#5A3622"><circle cx="40" cy="42" r="4"/><circle cx="58" cy="38" r="4"/><circle cx="52" cy="58" r="4"/><circle cx="38" cy="60" r="3.4"/><circle cx="64" cy="55" r="3.4"/></g>',
    crumbs: '<g fill="#D9A15E" ' + S.replace('stroke-width="3"', 'stroke-width="1.5"') + '><circle cx="30" cy="60" r="5"/><circle cx="52" cy="50" r="4"/><circle cx="68" cy="64" r="5.5"/><circle cx="46" cy="72" r="3.5"/><circle cx="76" cy="46" r="3"/></g>',
    cat: '<g ' + S + '><path d="M22 90 Q16 52 40 44 Q50 40 60 44 Q84 52 78 90Z" fill="#F29A4A"/><path d="M34 46 L30 24 L44 38Z M66 46 L70 24 L56 38Z" fill="#F29A4A"/><path d="M78 88 Q98 80 92 56" fill="none" stroke="#F29A4A" stroke-width="8"/></g><circle cx="42" cy="56" r="2.6" fill="' + INK + '"/><circle cx="58" cy="56" r="2.6" fill="' + INK + '"/><path d="M46 63 Q50 67 54 63" stroke="' + INK + '" stroke-width="2.4" fill="none"/>',
    door: '<g ' + S + '><rect x="14" y="4" width="72" height="94" rx="30" ry="30" fill="#3E7FD0"/><rect x="28" y="24" width="44" height="64" rx="18" fill="#2F66AD"/></g><circle cx="68" cy="58" r="4" fill="#F2B84B"/>',
    paw: '<g fill="#2B2F3A"><ellipse cx="50" cy="66" rx="22" ry="18"/><ellipse cx="24" cy="42" rx="8" ry="11"/><ellipse cx="42" cy="32" rx="8" ry="11"/><ellipse cx="60" cy="32" rx="8" ry="11"/><ellipse cx="77" cy="42" rx="8" ry="11"/></g>',
    flour: '<g ' + S + '><path d="M24 40 Q50 30 76 40 L80 92 Q50 100 20 92Z" fill="#E8C98E"/><path d="M26 44 Q50 36 74 44 Q64 54 50 50 Q36 54 26 44Z" fill="#fff"/></g><g fill="#fff" opacity=".9"><circle cx="30" cy="26" r="6"/><circle cx="46" cy="18" r="7"/><circle cx="64" cy="24" r="6"/><circle cx="76" cy="14" r="4"/></g>',
    magnifier: '<g ' + S + '><circle cx="40" cy="40" r="26" fill="#DDF1F7" fill-opacity=".7"/><path d="M60 60 L88 88" stroke-width="9"/></g><path d="M26 34 Q30 26 38 24" stroke="#fff" stroke-width="3.4" fill="none" stroke-linecap="round"/>',
    bulb: '<g ' + S + '><path d="M50 8 Q78 8 78 36 Q78 52 64 62 L64 74 L36 74 L36 62 Q22 52 22 36 Q22 8 50 8Z" fill="#FFD84A"/><rect x="38" y="76" width="24" height="9" rx="3" fill="#C9CED8"/></g><g stroke="#F2B84B" stroke-width="3.4" stroke-linecap="round"><path d="M50 -2 V-6 M10 12 L6 8 M90 12 L94 8"/></g>',
    question: '<text x="50" y="82" text-anchor="middle" font-family="Fredoka,sans-serif" font-weight="700" font-size="96" fill="#8B5CF6" stroke="#fff" stroke-width="4" paint-order="stroke">?</text>',
    exclaim: '<text x="50" y="82" text-anchor="middle" font-family="Fredoka,sans-serif" font-weight="700" font-size="96" fill="#FF7A2F" stroke="#fff" stroke-width="4" paint-order="stroke">!</text>',
    tick: '<circle cx="50" cy="50" r="40" fill="#1FB57A"/><path d="M28 52 L44 68 L74 34" stroke="#fff" stroke-width="10" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    cross: '<circle cx="50" cy="50" r="40" fill="#E5484D"/><path d="M32 32 L68 68 M68 32 L32 68" stroke="#fff" stroke-width="10" stroke-linecap="round"/>',
    book: '<g ' + S + '><path d="M8 24 Q30 14 50 26 Q70 14 92 24 V78 Q70 68 50 80 Q30 68 8 78Z" fill="#FFF7E6"/><path d="M50 26 V80"/></g><g stroke="#C9B48A" stroke-width="2.4"><path d="M16 38 Q30 32 42 40 M16 50 Q30 44 42 52 M58 40 Q70 32 84 38 M58 52 Q70 44 84 50"/></g>',
    coin: '<circle cx="50" cy="50" r="38" fill="#F2B84B" ' + S + '/><circle cx="50" cy="50" r="27" fill="none" stroke="#C98B1F" stroke-width="3"/><path d="M42 56 L50 38 L58 56Z" fill="#C98B1F"/>',
    cup: '<g ' + S + '><path d="M20 34 H72 V62 Q72 84 46 84 Q20 84 20 62Z" fill="#FF4F8B"/><path d="M72 40 Q92 40 90 56 Q88 68 70 66" fill="none" stroke-width="5"/><ellipse cx="46" cy="34" rx="26" ry="6" fill="#6B3F26"/></g><path d="M36 22 Q30 12 38 4 M52 22 Q46 12 54 4" stroke="#C9CED8" stroke-width="3.4" fill="none" stroke-linecap="round"/>',
    star: '<path d="M50 6 L62 36 L94 38 L69 58 L78 90 L50 72 L22 90 L31 58 L6 38 L38 36Z" fill="#FFC92E" ' + S + '/>',
    heart: '<path d="M50 88 C10 58 12 20 34 20 C44 20 50 28 50 34 C50 28 56 20 66 20 C88 20 90 58 50 88Z" fill="#FF4F8B" ' + S + '/>',
    clock: '<circle cx="50" cy="50" r="40" fill="#fff" ' + S + '/><path d="M50 50 V24 M50 50 L68 60" stroke="' + INK + '" stroke-width="5" stroke-linecap="round"/><circle cx="50" cy="50" r="4" fill="' + INK + '"/>',
    cloud: '<path d="M26 70 Q8 70 10 54 Q12 40 28 42 Q30 22 52 24 Q70 24 72 40 Q92 38 92 56 Q92 70 74 70Z" fill="#fff" stroke="#C9D3E3" stroke-width="3"/>',
    rain: '<path d="M26 70 Q8 70 10 54 Q12 40 28 42 Q30 22 52 24 Q70 24 72 40 Q92 38 92 56 Q92 70 74 70Z" fill="#9AA6B8"/><g stroke="#3E7FD0" stroke-width="4" stroke-linecap="round"><path d="M28 78 L24 92 M48 78 L44 92 M68 78 L64 92"/></g>',
    sun: '<circle cx="50" cy="50" r="22" fill="#FFC92E"/><g stroke="#FFC92E" stroke-width="6" stroke-linecap="round"><path d="M50 8 V18 M50 82 V92 M8 50 H18 M82 50 H92 M20 20 L27 27 M73 73 L80 80 M80 20 L73 27 M27 73 L20 80"/></g>',
    moon: '<path d="M64 10 A40 40 0 1 0 90 66 A32 32 0 1 1 64 10Z" fill="#FFF3C7"/>',
    coffee: '<g ' + S + '><path d="M20 34 H72 V62 Q72 84 46 84 Q20 84 20 62Z" fill="#FF4F8B"/><path d="M72 40 Q92 40 90 56 Q88 68 70 66" fill="none" stroke-width="5"/><ellipse cx="46" cy="34" rx="26" ry="6" fill="#6B3F26"/></g>',
    chart: '<g ' + S + '><path d="M10 8 V90 H94" fill="none"/><rect x="22" y="56" width="16" height="34" fill="#9AA6B8"/><rect x="46" y="40" width="16" height="50" fill="#9AA6B8"/><rect x="70" y="20" width="16" height="70" fill="#FF4F8B"/></g>',
    news: '<g ' + S + '><rect x="12" y="14" width="76" height="72" rx="6" fill="#FFFDF6"/><path d="M22 28 H78 M22 42 H50 M22 54 H50 M22 66 H50" fill="none"/><rect x="56" y="38" width="22" height="30" fill="#DDE6F3"/></g>',
    arrow: '<path d="M10 50 H78 M54 24 L82 50 L54 76" stroke="' + INK + '" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    bed: '<g ' + S + '><rect x="8" y="50" width="84" height="30" rx="8" fill="#8EA7D8"/><rect x="8" y="34" width="22" height="46" rx="8" fill="#6F89BD"/><rect x="34" y="44" width="30" height="14" rx="7" fill="#FFF"/></g>',
    window: '<g ' + S + '><rect x="12" y="8" width="76" height="84" rx="6" fill="#CDEBFF"/><path d="M50 8 V92 M12 50 H88"/></g>',
    tree: '<rect x="44" y="60" width="12" height="38" fill="#8A5A3C"/><circle cx="50" cy="38" r="30" fill="#4FA35B"/><circle cx="38" cy="30" r="5" fill="#E5484D"/><circle cx="60" cy="44" r="5" fill="#E5484D"/><circle cx="52" cy="24" r="5" fill="#E5484D"/>',
    house: '<g ' + S + '><path d="M10 48 L50 14 L90 48 V92 H10Z" fill="#F6EBD3"/><rect x="40" y="58" width="20" height="34" rx="10" fill="#3E7FD0"/></g>',
    stork: '<g ' + S + '><path d="M44 62 Q40 40 56 34 L74 30 L56 40 Q52 52 54 62Z" fill="#fff"/><path d="M74 30 L96 28 L76 36Z" fill="#E5484D"/><path d="M46 62 L40 96 M54 62 L58 96" stroke="#E5484D" stroke-width="3"/><path d="M44 54 Q26 52 24 64 Q40 70 48 60Z" fill="#2B2F3A"/></g>',
    pram: '<g ' + S + '><path d="M14 54 H78 Q78 80 46 80 Q14 80 14 54Z" fill="#FF8FB5"/><path d="M14 54 Q20 30 54 28 V54Z" fill="#FF6FA1"/><circle cx="28" cy="88" r="8" fill="#fff"/><circle cx="66" cy="88" r="8" fill="#fff"/><path d="M78 54 L90 30" fill="none"/></g>',
    dice: '<g ' + S + '><rect x="14" y="14" width="72" height="72" rx="14" fill="#fff"/></g><g fill="' + INK + '"><circle cx="34" cy="34" r="6"/><circle cx="66" cy="34" r="6"/><circle cx="50" cy="50" r="6"/><circle cx="34" cy="66" r="6"/><circle cx="66" cy="66" r="6"/></g>',
    people: '<g fill="#7B8BA6"><circle cx="28" cy="38" r="12"/><rect x="14" y="52" width="28" height="36" rx="12"/><circle cx="72" cy="38" r="12"/><rect x="58" y="52" width="28" height="36" rx="12"/></g><circle cx="50" cy="30" r="12" fill="#F2B84B"/><rect x="36" y="44" width="28" height="44" rx="12" fill="#F2B84B"/>'
  };
  var BGS = {
    plain: '<rect width="160" height="90" fill="#FFF6E5"/>',
    field: '<defs><linearGradient id="gF" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#9ED8FF"/><stop offset="1" stop-color="#FFF1C9"/></linearGradient></defs><rect width="160" height="90" fill="url(#gF)"/><circle cx="130" cy="20" r="9" fill="#FFD66B"/><path d="M0 62 Q40 38 80 56 T160 50 V90 H0Z" fill="#9BCB7A"/><path d="M0 74 Q50 58 100 72 T160 68 V90 H0Z" fill="#7DB863"/>',
    night: '<defs><linearGradient id="gN" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#1D2B52"/><stop offset="1" stop-color="#3B3F7A"/></linearGradient></defs><rect width="160" height="90" fill="url(#gN)"/><path d="M120 10 A12 12 0 1 0 134 28 A9 9 0 1 1 120 10Z" fill="#FFF3C7"/><g fill="#fff"><circle cx="20" cy="14" r="1"/><circle cx="48" cy="26" r="1.2"/><circle cx="84" cy="10" r="1"/><circle cx="104" cy="30" r="1"/><circle cx="30" cy="40" r="1"/></g><rect y="70" width="160" height="20" fill="#2A2F55"/>',
    room: '<rect width="160" height="90" fill="#FBE7C6"/><rect y="64" width="160" height="26" fill="#C98F5B"/><rect x="18" y="14" width="34" height="36" rx="4" fill="#CDEBFF" stroke="#8A5A3C" stroke-width="2.4"/><path d="M35 14 V50 M18 32 H52" stroke="#8A5A3C" stroke-width="2"/><g stroke="#8A5A3C" stroke-width="2"><rect x="104" y="22" width="30" height="24" rx="2" fill="#FFF3C7"/><path d="M108 40 L116 32 L122 38 L128 30 L132 40Z" fill="#7DB863" stroke="none"/></g>',
    town: '<defs><linearGradient id="gT" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#B8E2FF"/><stop offset="1" stop-color="#FFF6E5"/></linearGradient></defs><rect width="160" height="90" fill="url(#gT)"/><g fill="#F6EBD3" stroke="#D9C9A5" stroke-width="1"><rect x="6" y="38" width="30" height="40"/><rect x="44" y="28" width="26" height="50"/><rect x="104" y="34" width="24" height="44"/><rect x="132" y="42" width="24" height="36"/></g><g fill="#3E7FD0"><rect x="12" y="52" width="8" height="12" rx="4"/><rect x="52" y="48" width="8" height="12" rx="4"/><rect x="110" y="52" width="8" height="12" rx="4"/></g><rect y="74" width="160" height="16" fill="#E7D7B5"/>',
    sky: '<defs><linearGradient id="gS" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7EC6FF"/><stop offset="1" stop-color="#E6F5FF"/></linearGradient></defs><rect width="160" height="90" fill="url(#gS)"/>',
    desk: '<rect width="160" height="90" fill="#EFE7D6"/><rect y="66" width="160" height="24" fill="#B98152"/>',
    cafe: '<rect width="160" height="90" fill="#FBE7C6"/><rect y="68" width="160" height="22" fill="#B98152"/><path d="M0 0 H160 V10 Q150 18 140 10 Q130 18 120 10 Q110 18 100 10 Q90 18 80 10 Q70 18 60 10 Q50 18 40 10 Q30 18 20 10 Q10 18 0 10Z" fill="#E5484D"/>'
  };
  window.Puppets = {
    actor: function (who) { return (WHOS[who] || WHOS.person)(); },
    prop: function (what) { return '<svg viewBox="0 0 100 100" class="pr" aria-hidden="true">' + (PROPS[what] || "") + "</svg>"; },
    bg: function (name) { return '<svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" class="bgsvg" aria-hidden="true">' + (BGS[name] || BGS.plain) + "</svg>"; },
    names: { actors: Object.keys(WHOS), props: Object.keys(PROPS), bgs: Object.keys(BGS) }
  };
})();
