/*
 * Closer AI — website analytics
 * ------------------------------------------------------------------
 * PostHog, configured for a privacy-first, cookieless setup:
 *   - persistence: 'memory'  -> no cookies, no localStorage (no consent banner)
 *   - autocapture off        -> we only send the events we choose
 *   - reverse-proxied via /ingest (see vercel.json) so requests come
 *     from our own domain and survive ad-blockers
 *
 * TO ACTIVATE: paste your PostHog *public* project key (phc_...) below.
 * Until then this file is inert — it upgrades the forms to AJAX but
 * sends no analytics.
 *
 * US cloud is assumed. On EU cloud, change the rewrite hosts in
 * vercel.json to eu.i.posthog.com / eu-assets.i.posthog.com and set
 * ui_host below to https://eu.posthog.com.
 */
(function () {
  'use strict';

  var POSTHOG_KEY = 'phc_wzEf7hLtCkSUKkfq3V3naHiz5XSnDA9RpvuEHDWT7ieB';
  var keyIsReal = POSTHOG_KEY.indexOf('phc_') === 0 && POSTHOG_KEY.indexOf('REPLACE') === -1;

  // --- PostHog init (only when a real key is present) ----------------
  if (keyIsReal) {
    !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug getPageViewId".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);

    window.posthog.init(POSTHOG_KEY, {
      api_host: '/ingest',
      ui_host: 'https://us.posthog.com',
      persistence: 'memory',          // cookieless
      autocapture: false,             // explicit events only
      capture_pageview: true,
      capture_pageleave: true,
      disable_session_recording: true,
      person_profiles: 'identified_only',
      respect_dnt: true
    });
  }

  // --- Helpers -------------------------------------------------------
  function capture(event, props) {
    try {
      if (window.posthog && typeof window.posthog.capture === 'function') {
        window.posthog.capture(event, props);
      }
    } catch (e) { /* never let analytics break the page */ }
  }

  function showSuccess(form) {
    var msg = document.createElement('p');
    msg.className = 'form-success';
    msg.textContent = "You're on the list — we'll be in touch.";
    form.replaceWith(msg);
  }

  function showError(form, btn) {
    if (btn) {
      btn.disabled = false;
      if (btn.dataset.label) btn.textContent = btn.dataset.label;
    }
    var err = form.querySelector('.form-error');
    if (!err) {
      err = document.createElement('p');
      err.className = 'form-error';
      form.appendChild(err);
    }
    err.textContent = 'Something went wrong — please try again.';
  }

  // --- Form handling: AJAX submit + conversion event -----------------
  function wireForm(form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var location = form.getAttribute('data-form-location') || 'unknown';
      var btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.dataset.label = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Sending…';
      }
      fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'Accept': 'application/json' }
      }).then(function (res) {
        if (res.ok) {
          capture('early_access_submitted', { location: location });
          showSuccess(form);
        } else {
          showError(form, btn);
        }
      }).catch(function () {
        showError(form, btn);
      });
    });
  }

  function init() {
    var forms = document.querySelectorAll('form.early-access-form');
    for (var i = 0; i < forms.length; i++) wireForm(forms[i]);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
