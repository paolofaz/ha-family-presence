# Dashboard RC1 — visualizzazione in ora italiana

La logica FSM, le decisioni e gli snapshot **restano in UTC**. Non
modificare i timestamp nel motore solo per farli leggere nella dashboard.
I template di Home Assistant possono mostrarli nel **fuso locale
configurato nell'istanza** (Europe/Rome), rispettando ora legale e solare.

Sostituzioni sicure per la scheda Markdown Lovelace:

```jinja
{# Ultimo cambiamento di una persona #}
{% set ts = state_attr('sensor.family_presence_shadow_paolo', 'last_transition') %}
{{ (as_timestamp(ts) | timestamp_custom('%d/%m/%Y %H:%M:%S', true)) if ts else '—' }}

{# Ultima forzatura manuale #}
{% set ts = state_attr('sensor.family_presence_shadow_paolo', 'manual_last_action_at') %}
{{ (as_timestamp(ts) | timestamp_custom('%d/%m %H:%M', true)) if ts else '—' }}

{# Ora dell'ultimo evento ignorato #}
{% set ts = state_attr('sensor.family_presence_shadow_paolo', 'last_ignored_at') %}
{{ (as_timestamp(ts) | timestamp_custom('%d/%m %H:%M', true)) if ts else '—' }}

{# Eventi recenti: mostra ora locale di ogni timestamp UTC #}
{% set events = state_attr('sensor.family_presence_shadow_paolo', 'recent_events') or [] %}
{% for event in events[-3:] %}
- {{ event.event }} · {{ event.outcome }} ·
  {{ as_timestamp(event.at) | timestamp_custom('%d/%m %H:%M:%S', true) }}
  · {{ event.reason }}
{% endfor %}
```

Il parametro `true` di `timestamp_custom` chiede esplicitamente
l'ora locale di Home Assistant. Non codificare una differenza UTC+1:
in estate l'Italia usa UTC+2.

Questa è **solo una trasformazione di presentazione**.
Il registro di eventi e lo stato FSM memorizzano l'istante assoluto,
non un orario locale ambiguo durante il cambio ora.
