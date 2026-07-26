/**
 * Thin wrapper over Telegram.WebApp shared by every Mini App.
 *
 * Two rules it enforces:
 *  1. initData is sent to the server on every call and never parsed here —
 *     the client cannot be trusted to say who the user is.
 *  2. The app degrades to a plain web page when opened outside Telegram,
 *     so a broken link shows an explanation instead of a blank screen.
 */
(function (global) {
  'use strict';

  const wa = global.Telegram && global.Telegram.WebApp;
  const inTelegram = Boolean(wa && wa.initData);

  const TG = {
    inTelegram,
    raw: wa || null,
    user: (wa && wa.initDataUnsafe && wa.initDataUnsafe.user) || null,
    startParam: (wa && wa.initDataUnsafe && wa.initDataUnsafe.start_param) || '',

    init(options) {
      const opts = options || {};
      if (!wa) return false;
      wa.ready();
      wa.expand();
      if (wa.enableClosingConfirmation && opts.confirmClose) {
        wa.enableClosingConfirmation();
      }
      this.applyTheme();
      wa.onEvent && wa.onEvent('themeChanged', () => this.applyTheme());
      return true;
    },

    /** Mirror Telegram's palette onto CSS variables so CSS stays declarative. */
    applyTheme() {
      if (!wa || !wa.themeParams) return;
      const root = document.documentElement;
      const map = {
        '--tg-bg': 'bg_color',
        '--tg-text': 'text_color',
        '--tg-hint': 'hint_color',
        '--tg-link': 'link_color',
        '--tg-button': 'button_color',
        '--tg-button-text': 'button_text_color',
        '--tg-secondary-bg': 'secondary_bg_color'
      };
      Object.keys(map).forEach((cssVar) => {
        const value = wa.themeParams[map[cssVar]];
        if (value) root.style.setProperty(cssVar, value);
      });
      root.dataset.scheme = wa.colorScheme || 'light';
    },

    /** Authenticated call. The server verifies X-Init-Data before answering. */
    async api(path, body) {
      const response = await fetch(path, {
        method: body === undefined ? 'GET' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Init-Data': (wa && wa.initData) || ''
        },
        body: body === undefined ? undefined : JSON.stringify(body)
      });

      let data = null;
      try {
        data = await response.json();
      } catch (err) {
        data = null;
      }

      if (!response.ok) {
        const detail = (data && data.detail) || `HTTP ${response.status}`;
        throw new Error(detail);
      }
      return data;
    },

    mainButton(text, handler) {
      if (!wa || !wa.MainButton) return null;
      const button = wa.MainButton;
      button.setText(text);
      button.show();
      if (this._mainHandler) button.offClick(this._mainHandler);
      this._mainHandler = handler;
      button.onClick(handler);
      return button;
    },

    hideMainButton() {
      if (wa && wa.MainButton) wa.MainButton.hide();
    },

    backButton(handler) {
      if (!wa || !wa.BackButton) return;
      wa.BackButton.show();
      if (this._backHandler) wa.BackButton.offClick(this._backHandler);
      this._backHandler = handler;
      wa.BackButton.onClick(handler);
    },

    hideBackButton() {
      if (wa && wa.BackButton) wa.BackButton.hide();
    },

    haptic(style) {
      if (!wa || !wa.HapticFeedback) return;
      if (style === 'success' || style === 'error' || style === 'warning') {
        wa.HapticFeedback.notificationOccurred(style);
      } else {
        wa.HapticFeedback.impactOccurred(style || 'light');
      }
    },

    alert(message) {
      if (wa && wa.showAlert) wa.showAlert(message);
      else global.alert(message);
    },

    confirm(message) {
      return new Promise((resolve) => {
        if (wa && wa.showConfirm) wa.showConfirm(message, resolve);
        else resolve(global.confirm(message));
      });
    },

    close() {
      if (wa && wa.close) wa.close();
    },

    /** Money formatting kept in one place so every app agrees. */
    money(amount, currency) {
      const value = Number(amount) || 0;
      const symbols = { RUB: '₽', EUR: '€', USD: '$' };
      const symbol = symbols[currency] || currency || '';
      const body = Number.isInteger(value)
        ? value.toLocaleString('ru-RU')
        : value.toFixed(2);
      return currency === 'USD' ? `${symbol}${body}` : `${body} ${symbol}`;
    },

    escape(text) {
      const div = document.createElement('div');
      div.textContent = text == null ? '' : String(text);
      return div.innerHTML;
    },

    /** Standard "this must be opened from Telegram" screen. */
    requireTelegram(target) {
      if (inTelegram) return true;
      const node = target || document.body;
      node.innerHTML =
        '<div class="notice"><h2>Откройте в Telegram</h2>' +
        '<p>Это мини-приложение работает внутри Telegram. ' +
        'Запустите его кнопкой в боте.</p></div>';
      return false;
    }
  };

  global.TG = TG;
})(window);
