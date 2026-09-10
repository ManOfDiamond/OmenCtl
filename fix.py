import sys

with open('src/omen-gui/src/keyboardrgb.rs', 'r') as f:
    content = f.read()

# 1. Update get_zone_for_key
content = content.replace(
    'if name == "zone_0" { return 1; }',
    'if name == "zone_0" || name == "c1_btn" { return 1; }\n    if name == "global_color_btn" { return 8; }'
)
content = content.replace(
    'if name == "zone_1" { return 2; }',
    'if name == "zone_1" || name == "c2_btn" { return 2; }'
)
content = content.replace(
    'if name == "zone_2" { return 3; }',
    'if name == "zone_2" || name == "c3_btn" { return 3; }'
)
content = content.replace(
    'if name == "zone_3" { return 4; }',
    'if name == "zone_3" || name == "c4_btn" { return 4; }'
)

# 2. Remove giant buttons
old_layout_logic = """    if detected_mode == KeyboardMode::Victus1Zone {
        let visualizer_box = gtk::Box::builder().orientation(gtk::Orientation::Horizontal).spacing(8).margin_top(32).margin_bottom(32).halign(gtk::Align::Center).build();
        let btn = gtk::Button::builder().label(i18n::t("kb_color_map")).width_request(560).height_request(180).build();
        btn.add_css_class("kb-zone-btn");
        btn.set_widget_name("zone_all");
        buttons_map.borrow_mut().insert("zone_all".to_string(), btn.clone());
        visualizer_box.append(&btn);
        kb_card.append(&visualizer_box);
    } else if detected_mode == KeyboardMode::Omen4Zone {
        let visualizer_box = gtk::Box::builder().orientation(gtk::Orientation::Horizontal).spacing(16).margin_top(32).margin_bottom(32).halign(gtk::Align::Center).build();
        let zones = ["Left", "Center", "Right", "WASD"];
        let names = ["zone_0", "zone_1", "zone_2", "zone_3"];
        for i in 0..4 {
            let btn = gtk::Button::builder().label(zones[i]).width_request(130).height_request(180).build();
            btn.add_css_class("kb-zone-btn");
            btn.set_widget_name(names[i]);
            buttons_map.borrow_mut().insert(names[i].to_string(), btn.clone());
            visualizer_box.append(&btn);
        }
        kb_card.append(&visualizer_box);
    } else {
        for row_keys in &layout {"""

content = content.replace(old_layout_logic, "    for row_keys in &layout {")
content = content.replace("            kb_card.append(&row_box);\n        }\n    }\n    \n    let b_map_clone = buttons_map.clone();", "            kb_card.append(&row_box);\n        }\n    \n    let b_map_clone = buttons_map.clone();")

# 3. Add to buttons_map
old_insert = "    global_color_box.append(&global_color_label);"
new_insert = """    buttons_map.borrow_mut().insert("global_color_btn".to_string(), global_color_btn.clone());
    buttons_map.borrow_mut().insert("c1_btn".to_string(), c1_btn.clone());
    buttons_map.borrow_mut().insert("c2_btn".to_string(), c2_btn.clone());
    buttons_map.borrow_mut().insert("c3_btn".to_string(), c3_btn.clone());
    buttons_map.borrow_mut().insert("c4_btn".to_string(), c4_btn.clone());

    global_color_box.append(&global_color_label);"""
content = content.replace(old_insert, new_insert)

# 4. Replace cX_btn callbacks
for idx, btn in enumerate(["c1_btn", "c2_btn", "c3_btn", "c4_btn"]):
    zone = idx + 1
    old_c = f"""    let dyn_prov_{btn[:2]} = dyn_provider.clone();
    {btn}.connect_clicked(move |btn_ref| {{
        let dyn_local = dyn_prov_{btn[:2]}.clone();
        show_color_picker_popover(btn_ref, Rc::new(move |hex| {{
            let css_str = format!("#{btn} {{{{ background: {{}}; background-image: none; border: 1px solid rgba(255,255,255,0.4); }}}}\\n", hex);
            crate::daemon_client::set_color_sync({idx}, hex.clone());
            dyn_local.load_from_string(&css_str);
        }}));
    }});"""

    new_c = f"""    let dyn_prov_{btn[:2]} = dyn_provider.clone();
    let b_map_{btn[:2]} = buttons_map.clone();
    let kc_{btn[:2]} = key_colors.clone();
    {btn}.connect_clicked(move |btn_ref| {{
        let dyn_local = dyn_prov_{btn[:2]}.clone();
        let b_map_local = b_map_{btn[:2]}.clone();
        let kc_local = kc_{btn[:2]}.clone();
        show_color_picker_popover(btn_ref, Rc::new(move |hex| {{
            crate::daemon_client::set_color_sync({idx}, hex.clone());
            let map = b_map_local.borrow();
            for (k, _) in map.iter() {{
                if crate::keyboardrgb::get_zone_for_key(k) == {zone} {{
                    kc_local.borrow_mut().insert(k.clone(), hex.clone());
                }}
            }}
            let mut css_str = String::new();
            for (k, c) in kc_local.borrow().iter() {{
                if let Some(target_btn) = map.get(k) {{
                    let wname = target_btn.widget_name();
                    css_str.push_str(&format!("#{{}} {{{{ background: {{}}; background-image: none; }}}}\\n", wname.as_str(), c));
                    if k.starts_with("c") || k.starts_with("global_color") {{
                        css_str.push_str(&format!("#{{}} {{{{ border: 1px solid rgba(255,255,255,0.4); }}}}\\n", wname.as_str()));
                    }}
                }}
            }}
            dyn_local.load_from_string(&css_str);
        }}));
    }});"""
    content = content.replace(old_c, new_c)


# 5. Fix CSS rendering for Global Color button
# It currently has:
#             for (k, c) in kc_local.borrow().iter() {
#                 if let Some(target_btn) = b_map_local.borrow().get(k) {
#                     let wname = target_btn.widget_name();
#                     css_str.push_str(&format!("#{} {{ background: {}; background-image: none; }}\n", wname.as_str(), c));
#                 }
#             }
# We need to add the border logic there too!
old_css_loop = """            for (k, c) in kc_local.borrow().iter() {
                if let Some(target_btn) = b_map_local.borrow().get(k) {
                    let wname = target_btn.widget_name();
                    css_str.push_str(&format!("#{} {{ background: {}; background-image: none; }}\\n", wname.as_str(), c));
                }
            }"""
new_css_loop = """            for (k, c) in kc_local.borrow().iter() {
                if let Some(target_btn) = b_map_local.borrow().get(k) {
                    let wname = target_btn.widget_name();
                    css_str.push_str(&format!("#{} {{ background: {}; background-image: none; }}\\n", wname.as_str(), c));
                    if k.starts_with("c") || k.starts_with("global_color") {
                        css_str.push_str(&format!("#{} {{ border: 1px solid rgba(255,255,255,0.4); }}\\n", wname.as_str()));
                    }
                }
            }"""
content = content.replace(old_css_loop, new_css_loop)


with open('src/omen-gui/src/keyboardrgb.rs', 'w') as f:
    f.write(content)

print("Done")
