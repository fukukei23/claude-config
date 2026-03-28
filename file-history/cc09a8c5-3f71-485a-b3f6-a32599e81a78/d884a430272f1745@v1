/**
 * ============================================================
 * 予約管理システム - 全ファイル ペースト用
 * ============================================================
 * 使い方: docs/GAS_SETUP_GUIDE.md を参照し、
 * 各ブロックを GAS の対応する .gs ファイルにコピーして貼り付けてください。
 * またはこのファイル全体を Code.gs 1つに貼り付けても動作します。
 * ============================================================
 */

// ========== Code.gs ==========
/**
 * Reservation System - Main Entry Point
 *
 * Google Apps Script for LINE Bot + Stripe Integration
 *
 */

// Webhook entry point - handles both LINE and Stripe webhooks
function doPost(e) {
  var body = e.postData.contents;
  var signature = e.parameter.signature;

  // Parse X-Line-Signature header for LINE webhook verification
  var lineSignature = e.parameter['x-line-signature'];

  // Parse Stripe-Signature header for Stripe webhook verification
  var stripeSignature = e.parameter['stripe-signature'];

  var headers = {};
  if (lineSignature) {
    headers['x-line-signature'] = lineSignature;
  }
  if (stripeSignature) {
    headers['stripe-signature'] = stripeSignature;
  }

  // Route to appropriate handler
  if (lineSignature) {
    // LINE webhook event
    handleLineWebhook(body, headers);
  } else if (stripeSignature) {
    // Stripe webhook event
    handleStripeWebhook(body, headers);
  } else {
    // Unknown webhook
    Logger.log('Unknown webhook source');
    return createTextOutput('error', 'Unknown webhook');
  }

  return createTextOutput('success', 'Webhook processed');
}

/**
 * Handle LINE webhook events
 *
 */
function handleLineWebhook(body, headers) {
  // Verify LINE signature
  if (!verifyLineSignature(body, headers['x-line-signature'])) {
    return createTextOutput('error', 'Invalid LINE signature');
  }

  var data = JSON.parse(body);
  var events = data.events;

  if (!events || events.length === 0) {
    return createTextOutput('error', 'No events found');
  }

  for (var i = 0; i < events.length; i++) {
    try {
      handleLineEvent(events[i]);
    } catch (eventError) {
      Logger.log('handleLineEvent error: ' + eventError.toString());
      try {
        appendLogRow('ERROR', eventError.message || eventError.toString());
      } catch (logErr) {
        Logger.log('appendLogRow failed: ' + logErr.toString());
      }
    }
  }
}

/**
 * Handle Stripe webhook events
 *
 */
function handleStripeWebhook(body, headers) {
  // Verify Stripe signature
  if (!verifyStripeSignature(body, headers['stripe-signature'])) {
    return createTextOutput('error', 'Invalid Stripe signature');
  }

  var data = JSON.parse(body);
  var event = data;

  if (!event || !event.type) {
    return createTextOutput('error', 'No event data');
  }

  switch (event.type) {
    case 'payment_intent.succeeded':
      handlePaymentSuccess(event.data.object);
      break;
    case 'payment_intent.payment_failed':
      handlePaymentFailure(event.data.object);
      break;
    case 'charge.refunded':
      handleRefund(event.data.object);
      break;
    default:
      Logger.log('Unknown Stripe event type: ' + event.type);
  }
}

/**
 * Verify LINE webhook signature
 */
function verifyLineSignature(body, signature) {
  var secret = PropertiesService.getScriptProperties().getProperty('LINE_CHANNEL_SECRET');
  if (!secret) {
    Logger.log('LINE_CHANNEL_SECRET not configured');
    return false;
  }
  var expectedSignature = Utilities.computeHmacSha256Signature(body, secret);
  var actualSignature = signature;
  return actualSignature === expectedSignature;
}

/**
 * Verify Stripe webhook signature
 */
function verifyStripeSignature(body, signature) {
  var secret = PropertiesService.getScriptProperties().getProperty('STRIPE_WEBHOOK_SECRET');
  if (!secret) {
    Logger.log('STRIPE_WEBHOOK_SECRET not configured');
    return false;
  }
  var signatureParts = signature.split(',');
  var timestamp = parseInt(signatureParts[0]);
  var v1 = signatureParts[1].replace(/=/g, '');
  var expectedSignature = Utilities.computeHmacSha256Signature(
    'timestamp=' + timestamp + ',v1=' + v1 + ',signature=' + body,
    secret
  );
  var actualSignature = signature;
  return actualSignature === expectedSignature;
}

/**
 * Create webhook response output
 *
 */
function createTextOutput(status, message) {
  var output = {
    status: status,
    message: message
  };

  return ContentService.createTextOutput(JSON.stringify(output))
    .setMimeType(ContentService.MimeType.JSON);
}

// ========== config/ScriptProperties.gs ==========
/**
 * Script Properties Configuration
 *
 * Manages environment variables and system settings
 */

// Property keys
var PROPERTY_KEYS = {
  // LINE settings
  LINE_CHANNEL_ACCESS_TOKEN: 'LINE_CHANNEL_ACCESS_TOKEN',
  LINE_CHANNEL_SECRET: 'LINE_CHANNEL_SECRET',
  LINE_ADMIN_USER_ID: 'LINE_ADMIN_USER_ID',

  // Stripe settings
  STRIPE_API_KEY: 'STRIPE_API_KEY',
  STRIPE_WEBHOOK_SECRET: 'STRIPE_WEBHOOK_SECRET',

  // Google Sheets
  SPREADSHEET_ID: 'SPREADSHEET_ID',

  // System settings
  DEPOSIT_AMOUNT_JPY: 'DEPOSIT_AMOUNT_JPY',
  CANCELLATION_DEADLINE_HOURS: 'CANCELLATION_DEADLINE_HOURS',
  REMINDER_HOURS_BEFORE: 'REMINDER_HOURS_BEFORE',
  RESALE_NOTIFICATION_MINUTES: 'RESALE_NOTIFICATION_MINUTES',
  AVERAGE_UNIT_PRICE: 'AVERAGE_UNIT_PRICE',
  NO_SHOW_THRESHOLD: 'NO_SHOW_THRESHOLD',
  NO_SHOW_DEPOSIT_AMOUNT: 'NO_SHOW_DEPOSIT_AMOUNT',

  // Contact (for fallback "人間に問い合わせる")
  CONTACT_PHONE: 'CONTACT_PHONE',
  CONTACT_URL: 'CONTACT_URL'
};

/**
 * Get property value with default fallback
 */
function getProperty(key, defaultValue) {
  var value = PropertiesService.getScriptProperties().getProperty(key);
  return value !== null ? value : defaultValue;
}

/**
 * Set property value
 */
function setProperty(key, value) {
  PropertiesService.getScriptProperties().setProperty(key, String(value));
}

/**
 * Get LINE channel access token
 */
function getLineAccessToken() {
  return getProperty(PROPERTY_KEYS.LINE_CHANNEL_ACCESS_TOKEN);
}

/**
 * Get LINE channel secret
 */
function getLineChannelSecret() {
  return getProperty(PROPERTY_KEYS.LINE_CHANNEL_SECRET);
}

/**
 * Get LINE admin user ID
 */
function getLineAdminUserId() {
  return getProperty(PROPERTY_KEYS.LINE_ADMIN_USER_ID);
}

/**
 * Get Stripe API key
 */
function getStripeApiKey() {
  return getProperty(PROPERTY_KEYS.STRIPE_API_KEY);
}

/**
 * Get Stripe webhook secret
 */
function getStripeWebhookSecret() {
  return getProperty(PROPERTY_KEYS.STRIPE_WEBHOOK_SECRET);
}

/**
 * Get spreadsheet ID
 */
function getSpreadsheetId() {
  return getProperty(PROPERTY_KEYS.SPREADSHEET_ID);
}

/**
 * Get deposit amount in JPY
 */
function getDepositAmount() {
  return parseInt(getProperty(PROPERTY_KEYS.DEPOSIT_AMOUNT_JPY, '1000'));
}

/**
 * Get cancellation deadline in hours
 */
function getCancellationDeadlineHours() {
  return parseInt(getProperty(PROPERTY_KEYS.CANCELLATION_DEADLINE_HOURS, '2'));
}

/**
 * Get reminder hours before appointment
 */
function getReminderHoursBefore() {
  return parseInt(getProperty(PROPERTY_KEYS.REMINDER_HOURS_BEFORE, '24'));
}

/**
 * Get resale notification minutes
 */
function getResaleNotificationMinutes() {
  return parseInt(getProperty(PROPERTY_KEYS.RESALE_NOTIFICATION_MINUTES, '10'));
}

/**
 * Get average unit price
 */
function getAverageUnitPrice() {
  return parseInt(getProperty(PROPERTY_KEYS.AVERAGE_UNIT_PRICE, '6000'));
}

/**
 * Get no-show threshold
 */
function getNoShowThreshold() {
  return parseInt(getProperty(PROPERTY_KEYS.NO_SHOW_THRESHOLD, '2'));
}

/**
 * Get no-show deposit amount
 */
function getNoShowDepositAmount() {
  return parseInt(getProperty(PROPERTY_KEYS.NO_SHOW_DEPOSIT_AMOUNT, '2000'));
}

/**
 * Get contact phone for "人間に問い合わせる" message (optional)
 */
function getContactPhone() {
  return getProperty(PROPERTY_KEYS.CONTACT_PHONE, '');
}

/**
 * Get contact URL for "人間に問い合わせる" message (optional)
 */
function getContactUrl() {
  return getProperty(PROPERTY_KEYS.CONTACT_URL, '');
}

/**
 * Initialize default properties if not set
 */
function initializeDefaultProperties() {
  var defaults = {
    DEPOSIT_AMOUNT_JPY: '1000',
    CANCELLATION_DEADLINE_HOURS: '2',
    REMINDER_HOURS_BEFORE: '24',
    RESALE_NOTIFICATION_MINUTES: '10',
    AVERAGE_UNIT_PRICE: '6000',
    NO_SHOW_THRESHOLD: '2',
    NO_SHOW_DEPOSIT_AMOUNT: '2000'
  };

  var properties = PropertiesService.getScriptProperties();

  for (var key in defaults) {
    if (!properties.getProperty(key)) {
      properties.setProperty(key, defaults[key]);
      Logger.log('Initialized property: ' + key + ' = ' + defaults[key]);
    }
  }
}

/**
 * Check if all required properties are set
 */
function validateRequiredProperties() {
  var required = [
    PROPERTY_KEYS.LINE_CHANNEL_ACCESS_TOKEN,
    PROPERTY_KEYS.LINE_CHANNEL_SECRET,
    PROPERTY_KEYS.STRIPE_API_KEY,
    PROPERTY_KEYS.STRIPE_WEBHOOK_SECRET,
    PROPERTY_KEYS.SPREADSHEET_ID
  ];

  var missing = [];
  for (var i = 0; i < required.length; i++) {
    if (!getProperty(required[i])) {
      missing.push(required[i]);
    }
  }

  return {
    valid: missing.length === 0,
    missing: missing
  };
}

// ========== config/SheetConfig.gs ==========
/**
 * Sheet Configuration - Google Sheets Structure Definitions
 *
 * Defines sheet names and column mappings for the reservation system
 */

// Sheet names
var SHEET_NAMES = {
  RESERVATIONS: 'reservations',
  WAITLIST: 'waitlist',
  WEEKLY_SUMMARY: 'weekly_summary',
  LOG: 'ログ'
};

// Reservations sheet column indices (1-based)
var RESERVATIONS_COLUMNS = {
  RESERVATION_ID: 1,
  CREATED_AT: 2,
  PATIENT_NAME: 3,
  PHONE: 4,
  LINE_DISPLAY_NAME: 5,
  VISIT_TYPE: 6,
  MENU_TYPE: 7,
  RESERVED_DATE: 8,
  RESERVED_START: 9,
  RESERVED_END: 10,
  STATUS: 11,
  DEPOSIT_REQUIRED: 12,
  DEPOSIT_AMOUNT: 13,
  DEPOSIT_STATUS: 14,
  REMINDER_SENT: 15,
  REMINDER_RESPONSE: 16,
  CANCEL_TIME: 17,
  RESALE_NOTIFIED: 18,
  RESALE_SUCCESS: 19,
  AVERAGE_UNIT_PRICE: 20,
  NOTES: 21
};

// Reservations sheet headers
var RESERVATIONS_HEADERS = [
  'reservation_id', 'created_at', 'patient_name', 'phone', 'line_display_name',
  'visit_type', 'menu_type', 'reserved_date', 'reserved_start', 'reserved_end',
  'status', 'deposit_required', 'deposit_amount', 'deposit_status',
  'reminder_sent', 'reminder_response', 'cancel_time', 'resale_notified',
  'resale_success', 'average_unit_price', 'notes'
];

// Waitlist sheet column indices (1-based)
var WAITLIST_COLUMNS = {
  WAITLIST_ID: 1,
  LINE_DISPLAY_NAME: 2,
  PHONE: 3,
  PREFERRED_TIME: 4,
  SAME_DAY_OK: 5,
  LAST_NOTIFIED_AT: 6,
  NOTES: 7
};

// Waitlist sheet headers
var WAITLIST_HEADERS = [
  'waitlist_id', 'line_display_name', 'phone', 'preferred_time',
  'same_day_ok', 'last_notified_at', 'notes'
];

// Weekly Summary sheet column indices (1-based)
var WEEKLY_SUMMARY_COLUMNS = {
  WEEK_START: 1,
  TOTAL_RESERVATIONS: 2,
  TOTAL_NO_SHOWS: 3,
  NO_SHOW_RATE: 4,
  SAME_DAY_CANCELLATIONS: 5,
  RESALE_NOTIFICATIONS: 6,
  RESALE_SUCCESS_COUNT: 7,
  ESTIMATED_RECOVERED_REVENUE: 8
};

// Weekly Summary sheet headers
var WEEKLY_SUMMARY_HEADERS = [
  'week_start', 'total_reservations', 'total_no_shows', 'no_show_rate',
  'same_day_cancellations', 'resale_notifications', 'resale_success_count',
  'estimated_recovered_revenue'
];

// Log sheet headers (timestamp, level, message)
var LOG_HEADERS = ['timestamp', 'level', 'message'];

// Reservation status values
var RESERVATION_STATUS = {
  PENDING: 'Pending',
  CONFIRMED: 'Confirmed',
  VISITED: 'Visited',
  CANCELLED: 'Cancelled',
  NO_SHOW: 'NoShow'
};

// Deposit status values
var DEPOSIT_STATUS = {
  UNPAID: 'Unpaid',
  PAID: 'Paid',
  REFUNDED: 'Refunded',
  APPLIED: 'Applied',
  FORFEITED: 'Forfeited'
};

// Visit type values
var VISIT_TYPE = {
  FIRST: 'First',
  REPEAT: 'Repeat'
};

// Get column index by name
function getReservationColumn(columnName) {
  return RESERVATIONS_COLUMNS[columnName];
}

function getWaitlistColumn(columnName) {
  return WAITLIST_COLUMNS[columnName];
}

function getWeeklySummaryColumn(columnName) {
  return WEEKLY_SUMMARY_COLUMNS[columnName];
}

// ========== utils/ValidationUtils.gs ==========
/**
 * Normalize phone input (+81, hyphens, spaces, parens) for validation.
 */
function normalizePhoneInput(phone) {
  if (!phone || typeof phone !== 'string') return '';
  var s = phone.trim().replace(/[-\s()（）]/g, '');
  if (s.replace(/^\+81/, '0').length >= 10 && s.indexOf('+81') === 0) s = '0' + s.substring(3);
  return s;
}
function validatePhoneNumber(phone) {
  if (!phone || typeof phone !== 'string') return false;
  var cleaned = phone.replace(/[-\s]/g, '');
  return /^0\d{9,10}$/.test(cleaned);
}
function validateDate(dateString) {
  if (!dateString || typeof dateString !== 'string') return false;
  var patterns = [/^\d{4}-\d{1,2}-\d{1,2}$/, /^\d{1,2}\/\d{1,2}\/\d{4}$/, /^\d{4}\/\d{1,2}\/\d{1,2}$/];
  for (var i = 0; i < patterns.length; i++) { if (patterns[i].test(dateString)) return true; }
  return false;
}
/**
 * Normalize time input (e.g. "10" or "10時" -> "10:00")
 */
function normalizeTimeInput(timeString) {
  if (!timeString || typeof timeString !== 'string') return timeString;
  var s = timeString.trim().replace(/[）)]\s*$/, '');
  var onlyHour = /^([01]?[0-9]|2[0-3])$/;
  var hourJp = /^([01]?[0-9]|2[0-3])時(半)?$/;
  var hourMinJp = /^([01]?[0-9]|2[0-3])時([0-5]?[0-9])分?$/;
  var gozenGogo = /^(午前|午後|あさ|昼|よる)?\s*([01]?[0-9]|2[0-3])時(半|([0-5]?[0-9])分?)?$/;
  var amPm = /^([01]?[0-9]|2[0-3]):?([0-5][0-9])?\s*(am|pm|AM|PM)$/;
  if (onlyHour.test(s)) return s + ':00';
  var m = s.match(hourJp);
  if (m) return m[1] + (m[2] ? ':30' : ':00');
  m = s.match(hourMinJp);
  if (m) { var min = m[2].length === 1 ? '0' + m[2] : m[2]; return m[1] + ':' + min; }
  m = s.match(gozenGogo);
  if (m) {
    var hour = parseInt(m[2], 10);
    var suffix = (m[1] || '').toString();
    if (suffix.indexOf('午後') !== -1 || suffix.indexOf('昼') !== -1 || suffix === 'よる') { if (hour >= 1 && hour <= 11) hour += 12; }
    var mins = (m[3] === '半') ? '30' : (m[4] ? (m[4].length === 1 ? '0' + m[4] : m[4]) : '00');
    return hour + ':' + mins;
  }
  m = s.match(amPm);
  if (m) {
    var h = parseInt(m[1], 10);
    var mins = m[2] ? m[2] : '00';
    if ((m[3] || '').toLowerCase() === 'pm' && h >= 1 && h <= 11) h += 12;
    if ((m[3] || '').toLowerCase() === 'am' && h === 12) h = 0;
    return h + ':' + mins;
  }
  return s;
}
function validateTime(timeString) {
  if (!timeString || typeof timeString !== 'string') return false;
  if (!/^([01]?[0-9]|2[0-3]):[0-5][0-9]$/.test(timeString)) return false;
  var parts = timeString.split(':');
  var hours = parseInt(parts[0]), minutes = parseInt(parts[1]);
  return hours >= 0 && hours <= 23 && minutes >= 0 && minutes <= 59;
}
function validateEmail(email) { if (!email || typeof email !== 'string') return false; return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email); }
function validateVisitType(visitType) { return visitType === VISIT_TYPE.FIRST || visitType === VISIT_TYPE.REPEAT; }
function validateMenuType(menuType) {
  var validMenus = ['初診（30分）', '再診（30分）', '再診（60分）'];
  return validMenus.indexOf(menuType) !== -1;
}
function validateReservationStatus(status) {
  var validStatuses = [RESERVATION_STATUS.PENDING, RESERVATION_STATUS.CONFIRMED, RESERVATION_STATUS.VISITED, RESERVATION_STATUS.CANCELLED, RESERVATION_STATUS.NO_SHOW];
  return validStatuses.indexOf(status) !== -1;
}
function validateDepositStatus(depositStatus) {
  var validStatuses = [DEPOSIT_STATUS.UNPAID, DEPOSIT_STATUS.PAID, DEPOSIT_STATUS.REFUNDED, DEPOSIT_STATUS.APPLIED, DEPOSIT_STATUS.FORFEITED];
  return validStatuses.indexOf(depositStatus) !== -1;
}
function sanitizeInput(input) {
  if (!input || typeof input !== 'string') return '';
  return input.replace(/<[^>]*>/g, '').replace(/[<>]/g, '').trim();
}
function validateName(name) {
  if (!name || typeof name !== 'string') return false;
  var pattern = /^[\u3000-\u30FF\u4E00-\u9FAF\u0020-\u007E\s\u3001\u3002\u30FB\uFF0C\uFF0E\uFF1A\uFF1F]+$/;
  return name.length > 0 && name.length <= 50 && pattern.test(name);
}
function validateNotes(notes) { return !notes || notes.length <= 200; }
function validateCancellationReason(reason) { return reason && reason.length > 0 && reason.length <= 100; }
function formatPhoneNumber(phone) {
  if (!phone) return '';
  var cleaned = phone.replace(/[-\s]/g, '');
  if (cleaned.length === 10) return cleaned.replace(/(\d{3})(\d{3})(\d{4})/, '$1-$2-$3');
  if (cleaned.length === 11) return cleaned.replace(/(\d{3})(\d{4})(\d{4})/, '$1-$2-$3');
  return phone;
}
function validateAmount(amount) { var num = parseInt(amount); return !isNaN(num) && num > 0 && num <= 1000000; }

// ========== utils/DateUtils.gs ==========
/**
 * Date Utils - Date and Time Utilities
 */
function formatDate(date) { if (!date) return ''; return Utilities.formatDate(date, 'Asia/Tokyo', 'yyyy-MM-dd'); }
function formatTime(date) { if (!date) return ''; return Utilities.formatDate(date, 'Asia/Tokyo', 'HH:mm'); }
function formatDateTime(date) { if (!date) return ''; return Utilities.formatDate(date, 'Asia/Tokyo', 'yyyy-MM-dd HH:mm'); }
function parseDate(dateString) {
  if (!dateString) return null;
  var formats = ['yyyy-MM-dd', 'yyyy/MM/dd', 'MM/dd/yyyy', 'dd/MM/yyyy'];
  for (var i = 0; i < formats.length; i++) { try { return Utilities.parseDate(dateString, 'Asia/Tokyo', formats[i]); } catch (e) { } }
  return null;
}
function parseTime(timeString) {
  if (!timeString) return null;
  var parts = timeString.split(':'); if (parts.length !== 2) return null;
  return { hours: parseInt(parts[0]), minutes: parseInt(parts[1]) };
}
function addDays(date, days) { var result = new Date(date); result.setDate(result.getDate() + days); return result; }
function addHours(date, hours) { var result = new Date(date); result.setHours(result.getHours() + hours); return result; }
function addMinutes(date, minutes) { var result = new Date(date); result.setMinutes(result.getMinutes() + minutes); return result; }
function getWeekStart(date) { var d = new Date(date); var day = d.getDay(); var diff = d.getDate() - day + (day === 0 ? -6 : 1); return new Date(d.setDate(diff)); }
function getWeekEnd(date) { return addDays(getWeekStart(date), 6); }
function isToday(date) { if (!date) return false; return formatDate(date) === formatDate(new Date()); }
function isTomorrow(date) { if (!date) return false; return formatDate(date) === formatDate(addDays(new Date(), 1)); }
function isPast(date) { if (!date) return false; return date < new Date(); }
function getDaysDifference(date1, date2) { return Math.round((date2 - date1) / (24 * 60 * 60 * 1000)); }
function getHoursDifference(date1, date2) { return Math.round((date2 - date1) / (60 * 60 * 1000)); }
function getMinutesDifference(date1, date2) { return Math.round((date2 - date1) / (60 * 1000)); }
function calculateEndTime(startTime, durationMinutes) {
  if (durationMinutes == null) durationMinutes = 30;
  var timeParts = parseTime(startTime); if (!timeParts) return '';
  var totalMinutes = timeParts.hours * 60 + timeParts.minutes + durationMinutes;
  var endHours = Math.floor(totalMinutes / 60), endMinutes = totalMinutes % 60;
  return String(endHours).padStart(2, '0') + ':' + String(endMinutes).padStart(2, '0');
}
function calculateDuration(startTime, endTime) {
  var startParts = parseTime(startTime), endParts = parseTime(endTime);
  if (!startParts || !endParts) return 0;
  return (endParts.hours * 60 + endParts.minutes) - (startParts.hours * 60 + startParts.minutes);
}
function formatDateJapanese(date) {
  if (!date) return '';
  var weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  return date.getFullYear() + '年' + (date.getMonth() + 1) + '月' + date.getDate() + '日（' + weekdays[date.getDay()] + '）';
}
function getAgeInDays(date) { if (!date) return 0; return Math.floor((Date.now() - date.getTime()) / (24 * 60 * 60 * 1000)); }

// ========== templates/MessageTemplates.gs ==========
var MessageTemplates = {
  getWelcomeMessage: function() {
    return { text: '整骨院へようこそ！\n\n以下から選択してください：', quickReplies: [{label: '予約する', text: '予約する'}, {label: '予約変更・キャンセル', text: '予約変更・キャンセル'}, {label: '当日空き枠通知を受け取る', text: '当日空き枠通知を受け取る'}] };
  },
  getDepositRequestMessage: function(reservationId, date, time, menu, paymentLink) {
    return '以下の内容で予約を受け付けました。\n\n【予約ID】 ' + reservationId + '\n【日付】 ' + date + '\n【時間】 ' + time + '\n【施術】 ' + menu + '\n\nデポジット（' + getDepositAmount() + '円）のお支払いをお願いします。\n\n' + paymentLink + '\n\nお支払い完了後、「支払完了」と返信してください。';
  },
  getConfirmationMessage: function(reservation) {
    return '予約が確定しました！\n\n【予約ID】 ' + reservation.id + '\n【氏名】 ' + reservation.patient_name + '\n【日付】 ' + reservation.reserved_date + '\n【時間】 ' + reservation.reserved_start + ' - ' + reservation.reserved_end + '\n【施術】 ' + reservation.menu_type + '\n\n【注意事項】\n・遅刻は15分までにお願いします\n・キャンセルは2時間前までにお願いします\n・無断キャンセルの場合、デポジットは没収されます\n\n当日、' + reservation.reserved_start + 'にお待ちしております！';
  },
  getReminderMessage: function(date, time, menu) {
    return '明日はご予約の日です。\n\n【日時】 ' + date + ' ' + time + '\n【施術】 ' + menu + '\n\n来院できますか？\n\n返信してください：\n「行きます」または「変更したい」または「キャンセル」';
  },
  getSameDayConfirmationMessage: function(date, time) { return '本日は ' + date + ' の ' + time + ' にご予約です。\n\nご来院予定でよろしいでしょうか？'; },
  getResaleNotificationMessage: function(date, time, menu) {
    return '【当日空き枠のご案内】\n\n急な空き枠が出ました！\n\n【日時】 ' + date + ' ' + time + '\n【施術】 ' + menu + '\n\nご希望の方は「希望」と返信してください。\n先着順で確定させていただきます。';
  },
  getNoShowPenaltyMessage: function(depositAmount) {
    return '予約に来院されなかったため、デポジットを没収させていただきました。\n\n【没収金額】 ' + depositAmount + '円\n\n次回以降は必ずキャンセル連絡をお願いします。\n無断キャンセルが' + getNoShowThreshold() + '回以上の場合、次回以降は' + getNoShowDepositAmount() + '円のデポジットが必須となります。\n\n何かご不明な点がございましたら、ご連絡ください。';
  },
  getPaymentFailedMessage: function(errorMessage) {
    return 'お支払いに失敗しました。\n\n【エラー】 ' + (errorMessage || '原因不明のエラー') + '\n\n再度決済リンクからお支払いをお願いします。\n何度も失敗する場合は、管理者にお問い合わせください。';
  },
  getRefundConfirmationMessage: function(reservationId) {
    return 'デポジットを返金いたしました。\n\n【予約ID】 ' + reservationId + '\n【返金額】 ' + getDepositAmount() + '円\n\n返金処理には3〜5営業日かかります。\nご了承ください。';
  },
  getCancellationConfirmationMessage: function(reservationId) { return '予約をキャンセルしました。\n\n【予約ID】 ' + reservationId + '\n\nまたのご予約をお待ちしております。'; },
  getMenuOptionsMessage: function() { return '施術の種類を選択してください。\n\n1. 初診（30分）\n2. 再診（30分）\n3. 再診（60分）\n\n番号（1〜3）または施術名で返信してください。'; },
  getChangePromptMessage: function() { return '変更したい予約の電話番号を入力してください。\n\n該当する予約を検索します。'; },
  getCancelPromptMessage: function() { return 'キャンセルしたい予約の電話番号を入力してください。\n\n該当する予約を検索します。\n※キャンセルは2時間前まで無料です。'; },
  getWaitlistRegistrationMessage: function() { return '待機リストに登録します。\n\n以下の情報を入力してください。\n\n1. 電話番号\n2. 希望時間（Morning/Afternoon/Evening/Any）\n3. 当日空き枠でよいか（Y/N）'; },
  getContactMessage: function() {
    var phone = getContactPhone();
    var url = getContactUrl();
    var msg = 'お問い合わせありがとうございます。\n\n担当者から折り返しご連絡いたします。';
    if (phone) msg += '\n\n【電話】 ' + phone;
    if (url) msg += '\n【URL】 ' + url;
    if (!phone && !url) msg += '\n\nご不明な点はお気軽にご連絡ください。';
    return msg;
  },
  getWeeklySummaryMessage: function(weekData) {
    return '【週次サマリー】\n\n集計期間: ' + weekData.week_start + '\n\n総予約件数: ' + weekData.total_reservations + '\n無断件数: ' + weekData.total_no_shows + '\n無断率: ' + weekData.no_show_rate + '%\n当日キャンセル: ' + weekData.same_day_cancellations + '\n再販通知回数: ' + weekData.resale_notifications + '\n再販成功数: ' + weekData.resale_success_count + '\n推定回収額: ' + weekData.estimated_recovered_revenue + '円\n\n詳細はスプレッドシートをご確認ください。';
  }
};

// ========== models/Reservation.gs ==========
function createReservationObject(data) {
  return { id: data.reservation_id, created_at: data.created_at, patient_name: data.patient_name, phone: data.phone, line_display_name: data.line_display_name, visit_type: data.visit_type, menu_type: data.menu_type, reserved_date: data.reserved_date, reserved_start: data.reserved_start, reserved_end: data.reserved_end, status: data.status, deposit_required: data.deposit_required, deposit_amount: data.deposit_amount, deposit_status: data.deposit_status, reminder_sent: data.reminder_sent, reminder_response: data.reminder_response, cancel_time: data.cancel_time, resale_notified: data.resale_notified, resale_success: data.resale_success, average_unit_price: data.average_unit_price, notes: data.notes };
}
function validateReservationData(data) {
  var errors = [];
  if (!data.patient_name || data.patient_name.trim() === '') errors.push('患者名を入力してください。');
  if (!data.phone || !validatePhoneNumber(data.phone)) errors.push('電話番号の形式が正しくありません。');
  if (!data.reserved_date || !validateDate(data.reserved_date)) errors.push('日付の形式が正しくありません。');
  if (!data.reserved_start || !validateTime(data.reserved_start)) errors.push('時間の形式が正しくありません。');
  if (!data.menu_type || data.menu_type.trim() === '') errors.push('施術の種類を選択してください。');
  return { valid: errors.length === 0, errors: errors };
}
function canCancelReservation(reservation) {
  if (reservation.status === RESERVATION_STATUS.CANCELLED) return { canCancel: false, reason: '既にキャンセルされています。' };
  if (reservation.status === RESERVATION_STATUS.VISITED) return { canCancel: false, reason: '既に来院されています。' };
  if (reservation.status === RESERVATION_STATUS.NO_SHOW) return { canCancel: false, reason: '無断キャンセルとなっています。' };
  var now = new Date(); var reservedDateTime = new Date(reservation.reserved_date + 'T' + reservation.reserved_start + ':00');
  var hoursUntilReservation = (reservedDateTime - now) / (1000 * 60 * 60); var deadlineHours = getCancellationDeadlineHours();
  if (hoursUntilReservation < deadlineHours) return { canCancel: false, reason: 'キャンセル締切（' + deadlineHours + '時間前）を過ぎています。' };
  return { canCancel: true, reason: '' };
}
function calculateNoShowPenalty(reservation) {
  var userReservations = getReservationsByPatient(reservation.phone); var noShowCount = 0;
  for (var i = 0; i < userReservations.length; i++) { if (userReservations[i].status === RESERVATION_STATUS.NO_SHOW) noShowCount++; }
  if (noShowCount >= getNoShowThreshold()) return { isRepeatOffender: true, penaltyAmount: getNoShowDepositAmount() };
  return { isRepeatOffender: false, penaltyAmount: getDepositAmount() };
}
function formatReservationForDisplay(reservation) {
  return '【予約ID】 ' + reservation.id + '\n【氏名】 ' + reservation.patient_name + '\n【電話】 ' + reservation.phone + '\n【タイプ】 ' + (reservation.visit_type === VISIT_TYPE.FIRST ? '初診' : '再診') + '\n【施術】 ' + reservation.menu_type + '\n【日時】 ' + reservation.reserved_date + ' ' + reservation.reserved_start + '\n【ステータス】 ' + reservation.status + '\n【デポジット】 ' + reservation.deposit_status;
}
function getReservationDuration(reservation) {
  var startParts = reservation.reserved_start.split(':'), endParts = reservation.reserved_end.split(':');
  return (parseInt(endParts[0]) * 60 + parseInt(endParts[1])) - (parseInt(startParts[0]) * 60 + parseInt(startParts[1]));
}

// ========== models/Waitlist.gs ==========
function createWaitlistObject(data) { return { id: data.waitlist_id, line_display_name: data.line_display_name, phone: data.phone, preferred_time: data.preferred_time, same_day_ok: data.same_day_ok, last_notified_at: data.last_notified_at, notes: data.notes }; }
function validateWaitlistData(data) {
  var errors = [];
  if (!data.phone || !validatePhoneNumber(data.phone)) errors.push('電話番号の形式が正しくありません。');
  if (!data.preferred_time || data.preferred_time.trim() === '') errors.push('希望時間を入力してください。');
  if (data.same_day_ok !== 'Y' && data.same_day_ok !== 'N') errors.push('当日空き枠OK（Y/N）を選択してください。');
  return { valid: errors.length === 0, errors: errors };
}
function calculateMatchScore(waitlistEntry, appointmentDateTime) {
  var score = 0; var appointmentDate = new Date(appointmentDateTime); var appointmentHour = appointmentDate.getHours();
  if (waitlistEntry.same_day_ok === 'Y') score += 10;
  if (waitlistEntry.preferred_time === 'Any') score += 5; else if (waitlistEntry.preferred_time === 'Morning' && appointmentHour < 12) score += 5; else if (waitlistEntry.preferred_time === 'Afternoon' && appointmentHour >= 12 && appointmentHour < 17) score += 5; else if (waitlistEntry.preferred_time === 'Evening' && appointmentHour >= 17) score += 5;
  if (waitlistEntry.last_notified_at) { var lastNotified = new Date(waitlistEntry.last_notified_at); if ((Date.now() - lastNotified.getTime()) / (1000 * 60 * 60) < 24) score -= 5; }
  return score;
}
function sortWaitlistByMatch(waitlistEntries, appointmentDateTime) {
  return waitlistEntries.map(function(entry) { return { entry: entry, score: calculateMatchScore(entry, appointmentDateTime) }; }).sort(function(a, b) { return b.score - a.score; }).map(function(item) { return item.entry; });
}
function formatWaitlistForDisplay(waitlistEntry) {
  var sameDayText = waitlistEntry.same_day_ok === 'Y' ? '可' : '不可';
  return '【待機ID】 ' + waitlistEntry.id + '\n【表示名】 ' + waitlistEntry.line_display_name + '\n【電話】 ' + waitlistEntry.phone + '\n【希望時間】 ' + waitlistEntry.preferred_time + '\n【当日OK】 ' + sameDayText + '\n【最終通知】 ' + (waitlistEntry.last_notified_at || 'なし') + '\n【メモ】 ' + (waitlistEntry.notes || 'なし');
}
function getWaitlistCount() { var sheet = getWaitlistSheet(); return sheet.getLastRow() - 1; }
function isWaitlistEntryStale(waitlistEntry, daysToKeep) {
  if (!waitlistEntry.last_notified_at) return false;
  return (Date.now() - new Date(waitlistEntry.last_notified_at).getTime()) / (1000 * 60 * 60 * 24) > daysToKeep;
}

// ========== services/SheetService.gs ==========
function getReservationsSheet() { var ss = SpreadsheetApp.openById(getSpreadsheetId()); var sheet = ss.getSheetByName(SHEET_NAMES.RESERVATIONS); if (!sheet) sheet = createSheetWithHeaders(ss, SHEET_NAMES.RESERVATIONS, RESERVATIONS_HEADERS); return sheet; }
function getWaitlistSheet() { var ss = SpreadsheetApp.openById(getSpreadsheetId()); var sheet = ss.getSheetByName(SHEET_NAMES.WAITLIST); if (!sheet) sheet = createSheetWithHeaders(ss, SHEET_NAMES.WAITLIST, WAITLIST_HEADERS); return sheet; }
function getWeeklySummarySheet() { var ss = SpreadsheetApp.openById(getSpreadsheetId()); var sheet = ss.getSheetByName(SHEET_NAMES.WEEKLY_SUMMARY); if (!sheet) sheet = createSheetWithHeaders(ss, SHEET_NAMES.WEEKLY_SUMMARY, WEEKLY_SUMMARY_HEADERS); return sheet; }
function getLogSheet() { var ss = SpreadsheetApp.openById(getSpreadsheetId()); var sheet = ss.getSheetByName(SHEET_NAMES.LOG); if (!sheet) sheet = createSheetWithHeaders(ss, SHEET_NAMES.LOG, LOG_HEADERS); return sheet; }
function appendLogRow(level, message) { var safeMsg = (message || '').toString().replace(/\r?\n/g, ' ').substring(0, 500); var sheet = getLogSheet(); sheet.appendRow([new Date(), level || 'INFO', safeMsg]); }
function createSheetWithHeaders(ss, sheetName, headers) { var sheet = ss.insertSheet(sheetName); sheet.appendRow(headers); return sheet; }
function generateReservationId() { var sheet = getReservationsSheet(); var lastRow = sheet.getLastRow(); if (lastRow === 1) return 'R0001'; var lastId = sheet.getRange(lastRow, 1).getValue(); var newNumber = parseInt(lastId.substring(1)) + 1; return 'R' + String(newNumber).padStart(4, '0'); }
function createReservation(reservationData) {
  var sheet = getReservationsSheet(); var reservationId = generateReservationId(); var now = new Date();
  var row = [reservationId, now, reservationData.patient_name || '', reservationData.phone || '', reservationData.line_display_name || '', reservationData.visit_type || 'First', reservationData.menu_type || '', reservationData.reserved_date || '', reservationData.reserved_start || '', reservationData.reserved_end || '', reservationData.status || RESERVATION_STATUS.PENDING, reservationData.deposit_required || 'N', getDepositAmount(), reservationData.deposit_status || DEPOSIT_STATUS.UNPAID, 'N', '', '', 'N', 'N', getAverageUnitPrice(), reservationData.notes || ''];
  sheet.appendRow(row); return { id: reservationId, row_number: sheet.getLastRow() };
}
function updateReservation(reservationId, updates) {
  var sheet = getReservationsSheet(); var data = sheet.getDataRange().getValues(); var rowIndex = -1;
  for (var i = 1; i < data.length; i++) { if (data[i][0] === reservationId) { rowIndex = i + 1; break; } }
  if (rowIndex === -1) throw new Error('Reservation not found: ' + reservationId);
  for (var key in updates) { var columnIndex = RESERVATIONS_COLUMNS[key.toUpperCase()]; if (columnIndex) sheet.getRange(rowIndex, columnIndex).setValue(updates[key]); }
}
function getReservationById(reservationId) {
  var sheet = getReservationsSheet(); var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] === reservationId) return { id: data[i][0], created_at: data[i][1], patient_name: data[i][2], phone: data[i][3], line_display_name: data[i][4], visit_type: data[i][5], menu_type: data[i][6], reserved_date: data[i][7], reserved_start: data[i][8], reserved_end: data[i][9], status: data[i][10], deposit_required: data[i][11], deposit_amount: data[i][12], deposit_status: data[i][13], reminder_sent: data[i][14], reminder_response: data[i][15], cancel_time: data[i][16], resale_notified: data[i][17], resale_success: data[i][18], average_unit_price: data[i][19], notes: data[i][20], row_number: i + 1 };
  }
  return null;
}
function getReservationsByDate(date) { var sheet = getReservationsSheet(); var data = sheet.getDataRange().getValues(); var results = []; for (var i = 1; i < data.length; i++) { if (data[i][7] === date) results.push({ id: data[i][0], patient_name: data[i][2], phone: data[i][3], line_display_name: data[i][4], visit_type: data[i][5], menu_type: data[i][6], reserved_date: data[i][7], reserved_start: data[i][8], reserved_end: data[i][9], status: data[i][10] }); } return results; }
function getReservationsByPatient(phoneNumber) { var sheet = getReservationsSheet(); var data = sheet.getDataRange().getValues(); var results = []; for (var i = 1; i < data.length; i++) { if (data[i][3] === phoneNumber) results.push({ id: data[i][0], reserved_date: data[i][7], reserved_start: data[i][8], status: data[i][10] }); } return results; }
function getWaitlistReservations() { var sheet = getWaitlistSheet(); var data = sheet.getDataRange().getValues(); var results = []; for (var i = 1; i < data.length; i++) results.push({ id: data[i][0], line_display_name: data[i][1], phone: data[i][2], preferred_time: data[i][3], same_day_ok: data[i][4], last_notified_at: data[i][5] }); return results; }
function addToWaitlist(waitlistData) { var sheet = getWaitlistSheet(); var row = [sheet.getLastRow(), waitlistData.line_display_name || '', waitlistData.phone || '', waitlistData.preferred_time || 'Any', waitlistData.same_day_ok || 'N', '', waitlistData.notes || '']; sheet.appendRow(row); return sheet.getLastRow(); }
function markReminderSent(reservationId) { updateReservation(reservationId, { reminder_sent: 'Y' }); }
function markNoShow(reservationId) { updateReservation(reservationId, { status: RESERVATION_STATUS.NO_SHOW, deposit_status: DEPOSIT_STATUS.FORFEITED }); }
function handleCancellation(reservationId, reason) { updateReservation(reservationId, { status: RESERVATION_STATUS.CANCELLED, cancel_time: new Date() }); }
function findWaitlistCandidate(appointmentDateTime) {
  var waitlist = getWaitlistReservations(); var appointmentDate = new Date(appointmentDateTime); var hours = appointmentDate.getHours(); var candidates = [];
  for (var i = 0; i < waitlist.length; i++) {
    var entry = waitlist[i]; if (entry.last_notified_at && (Date.now() - new Date(entry.last_notified_at).getTime()) / (1000 * 60 * 60) < 24) continue;
    var timeMatch = (entry.preferred_time === 'Any') || (entry.preferred_time === 'Morning' && hours < 12) || (entry.preferred_time === 'Afternoon' && hours >= 12 && hours < 17) || (entry.preferred_time === 'Evening' && hours >= 17);
    candidates.push({ entry: entry, timeMatch: timeMatch, priority: entry.same_day_ok === 'Y' ? 1 : 0 });
  }
  candidates.sort(function(a, b) { if (a.priority !== b.priority) return b.priority - a.priority; return b.timeMatch - a.timeMatch; });
  return candidates.slice(0, 3).map(function(c) { return c.entry; });
}
function resellVacancy(reservationId, waitlistPatientId) { updateReservation(reservationId, { resale_notified: 'Y' }); }
function markResaleSuccessful(reservationId) { updateReservation(reservationId, { resale_success: 'Y' }); }

// ========== services/LineService.gs ==========
var LINE_API_URL = 'https://api.line.me/v2/bot/message/reply';
function sendLineReply(replyToken, text) { return sendLineMessages(replyToken, [{ type: 'text', text: text }]); }
function sendLineMessages(replyToken, messages) {
  var options = { method: 'post', contentType: 'application/json', headers: { 'Authorization': 'Bearer ' + getLineAccessToken() }, payload: JSON.stringify({ replyToken: replyToken, messages: messages }), muteHttpExceptions: true };
  var response = UrlFetchApp.fetch(LINE_API_URL, options); if (response.getResponseCode() !== 200) { Logger.log('LINE API Error: ' + response.getContentText()); return false; } return true;
}
function sendLinePush(userId, text) {
  var options = { method: 'post', contentType: 'application/json', headers: { 'Authorization': 'Bearer ' + getLineAccessToken() }, payload: JSON.stringify({ to: userId, messages: [{ type: 'text', text: text }] }), muteHttpExceptions: true };
  var response = UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', options); if (response.getResponseCode() !== 200) { Logger.log('LINE Push Error: ' + response.getContentText()); return false; } return true;
}
function getLineProfile(userId) { var options = { method: 'get', headers: { 'Authorization': 'Bearer ' + getLineAccessToken() }, muteHttpExceptions: true }; var response = UrlFetchApp.fetch('https://api.line.me/v2/bot/profile/' + userId, options); if (response.getResponseCode() !== 200) return null; return JSON.parse(response.getContentText()); }
function sendQuickReply(replyToken, text, quickReplies) {
  var message = { type: 'text', text: text, quickReply: { items: quickReplies.map(function(qr) { return { type: 'action', action: { type: 'message', label: qr.label, text: qr.text } }; }) } };
  return sendLineMessages(replyToken, [message]);
}
function logLineMessage(source, message) { Logger.log('LINE Message from ' + source.userId + ': ' + message); }

// ========== services/StripeService.gs ==========
var STRIPE_API_BASE = 'https://api.stripe.com/v1';
function createPaymentLink(reservationId, patientName, amount) {
  var apiKey = getStripeApiKey();
  var intentOptions = { method: 'post', contentType: 'application/x-www-form-urlencoded', headers: { 'Authorization': 'Bearer ' + apiKey }, payload: 'amount=' + amount + '&currency=jpy&metadata[reservation_id]=' + reservationId + '&metadata[patient_name]=' + encodeURIComponent(patientName) + '&payment_method_types[]=card', muteHttpExceptions: true };
  var intentResponse = UrlFetchApp.fetch(STRIPE_API_BASE + '/payment_intents', intentOptions);
  if (intentResponse.getResponseCode() !== 200) { Logger.log('Stripe Payment Intent Error: ' + intentResponse.getContentText()); return null; }
  var intent = JSON.parse(intentResponse.getContentText()); Logger.log('Created payment intent: ' + intent.id + ' for reservation: ' + reservationId); return intent.client_secret ? ('https://checkout.stripe.com/pay/' + intent.id) : null;
}
function getPaymentIntent(paymentIntentId) { var options = { method: 'get', headers: { 'Authorization': 'Bearer ' + getStripeApiKey() }, muteHttpExceptions: true }; var response = UrlFetchApp.fetch(STRIPE_API_BASE + '/payment_intents/' + paymentIntentId, options); if (response.getResponseCode() !== 200) return null; return JSON.parse(response.getContentText()); }
function handlePaymentSuccess(event) {
  var paymentIntent = event.data ? event.data.object : event; var reservationId = paymentIntent.metadata ? paymentIntent.metadata.reservation_id : null;
  if (!reservationId) return; var reservation = getReservationById(reservationId); if (!reservation) return;
  updateReservation(reservationId, { deposit_status: DEPOSIT_STATUS.PAID, status: RESERVATION_STATUS.CONFIRMED });
  var message = MessageTemplates.getConfirmationMessage(reservation); var lineUserId = reservation.line_display_name || reservation.phone; sendLinePush(lineUserId, message);
}
function handlePaymentFailure(event) { var paymentIntent = event.data ? event.data.object : event; var reservationId = paymentIntent.metadata ? paymentIntent.metadata.reservation_id : null; if (!reservationId) return; var reservation = getReservationById(reservationId); if (reservation) sendLinePush(reservation.line_display_name || reservation.phone, MessageTemplates.getPaymentFailedMessage(paymentIntent.last_payment_error ? paymentIntent.last_payment_error.message : '')); }

// ========== services/ReminderService.gs ==========
function sendDayBeforeReminders() {
  var sheet = getReservationsSheet(); var data = sheet.getDataRange().getValues(); var now = new Date(); var tomorrow = addDays(now, 1); var tomorrowStr = formatDate(tomorrow); var sentCount = 0;
  for (var i = 1; i < data.length; i++) {
    var r = data[i]; if (r[7] !== tomorrowStr || r[14] === 'Y' || r[10] !== RESERVATION_STATUS.CONFIRMED) continue;
    var msg = MessageTemplates.getReminderMessage(r[7], r[8], r[6]); var lineUserId = r[4] || r[3]; if (sendLinePush(lineUserId, msg)) { markReminderSent(r[0]); sentCount++; }
  }
  return sentCount;
}
function checkForNoShows() {
  var sheet = getReservationsSheet(); var data = sheet.getDataRange().getValues(); var now = new Date(); var currentTime = formatTime(now); var currentDate = formatDate(now); var noShowCount = 0;
  for (var i = 1; i < data.length; i++) {
    var r = data[i]; if (r[7] === currentDate && r[9] <= currentTime && r[10] === RESERVATION_STATUS.CONFIRMED) { markNoShow(r[0]); if (r[13] === DEPOSIT_STATUS.PAID) sendLinePush(r[4] || r[3], MessageTemplates.getNoShowPenaltyMessage(getNoShowDepositAmount())); noShowCount++; }
  }
  return noShowCount;
}
function handleSameDayCancellation(reservationId, reason) { var reservation = getReservationById(reservationId); if (!reservation) return; handleCancellation(reservationId, reason); var candidates = findWaitlistCandidate(reservation.reserved_date + ' ' + reservation.reserved_start); for (var i = 0; i < candidates.length; i++) { sendLinePush(candidates[i].line_display_name || candidates[i].phone, MessageTemplates.getResaleNotificationMessage(reservation.reserved_date, reservation.reserved_start, reservation.menu_type)); } if (candidates.length > 0) resellVacancy(reservationId, candidates[0].id); }
function cleanupWaitlist() { var sheet = getWaitlistSheet(); var data = sheet.getDataRange().getValues(); var thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000); var rowsToDelete = []; for (var i = 1; i < data.length; i++) { if (data[i][5] && new Date(data[i][5]) < thirtyDaysAgo) rowsToDelete.push(i + 1); } for (var j = rowsToDelete.length - 1; j >= 0; j--) sheet.deleteRow(rowsToDelete[j]); }

// ========== handlers/LineWebhookHandler.gs ==========
var USER_STATES = { IDLE: 'IDLE', AWAITING_NAME: 'AWAITING_NAME', AWAITING_PHONE: 'AWAITING_PHONE', AWAITING_DATE: 'AWAITING_DATE', AWAITING_TIME: 'AWAITING_TIME', AWAITING_TREATMENT: 'AWAITING_TREATMENT', AWAITING_PAYMENT: 'AWAITING_PAYMENT' };
var TEMP_DATA_KEY_PREFIX = 'user_temp_';
var FALLBACK_RETRY_TEXT = 'もう一度入力する';
var FALLBACK_CONTACT_TEXT = '人間に問い合わせる';
function sendFallbackWithContact(replyToken, errorMessage) {
  sendQuickReply(replyToken, errorMessage, [{ label: FALLBACK_RETRY_TEXT, text: FALLBACK_RETRY_TEXT }, { label: FALLBACK_CONTACT_TEXT, text: FALLBACK_CONTACT_TEXT }]);
}
function handleLineEvent(event) {
  var eventType = event.type; var source = event.source; var userId = source.userId; var replyToken = event.replyToken;
  switch (eventType) {
    case 'message': handleMessage(event.message, replyToken, userId); break;
    case 'follow': handleFollow(userId); break;
    case 'unfollow': handleUnfollow(userId); break;
    default: Logger.log('Unhandled event type: ' + eventType);
  }
}
function handleMessage(message, replyToken, userId) {
  if (message.type !== 'text') return;
  var text = message.text.trim(); var userState = getUserState(userId); logLineMessage({ userId: userId }, text);
  if (text === '人間に問い合わせる') { sendLineReply(replyToken, MessageTemplates.getContactMessage()); clearUserState(userId); return; }
  if (text.startsWith('/')) { handleCommand(text, replyToken, userId); return; }
  switch (userState.state) {
    case USER_STATES.IDLE: handleIdleState(text, replyToken, userId); break;
    case USER_STATES.AWAITING_NAME: handleAwaitingName(text, replyToken, userId); break;
    case USER_STATES.AWAITING_PHONE: handleAwaitingPhone(text, replyToken, userId); break;
    case USER_STATES.AWAITING_DATE: handleAwaitingDate(text, replyToken, userId); break;
    case USER_STATES.AWAITING_TIME: handleAwaitingTime(text, replyToken, userId); break;
    case USER_STATES.AWAITING_TREATMENT: handleAwaitingTreatment(text, replyToken, userId); break;
    case USER_STATES.AWAITING_PAYMENT: handleAwaitingPayment(text, replyToken, userId); break;
    default: sendLineReply(replyToken, '何かお手伝いしましょうか？');
  }
}
function handleCommand(command, replyToken, userId) {
  switch (command) {
    case '/reserve': startReservationFlow(replyToken, userId); break;
    case '/change': handleChangeFlow(replyToken, userId); break;
    case '/cancel': handleCancelFlow(replyToken, userId); break;
    case '/waitlist': handleWaitlistFlow(replyToken, userId); break;
    default: sendLineReply(replyToken, '無効なコマンドです。/reserve, /change, /cancel, /waitlist のいずれかを使用してください。');
  }
}
function startReservationFlow(replyToken, userId) { setUserState(userId, USER_STATES.AWAITING_NAME, {}); sendLineReply(replyToken, '予約を開始します。\n\nお名前を入力してください。'); }
function handleIdleState(text, replyToken, userId) {
  if (text === '予約する') startReservationFlow(replyToken, userId);
  else if (text === '予約変更・キャンセル') handleChangeFlow(replyToken, userId);
  else if (text === '当日空き枠通知を受け取る') handleWaitlistFlow(replyToken, userId);
  else { var w = MessageTemplates.getWelcomeMessage(); sendLineReply(replyToken, typeof w === 'string' ? w : w.text); }
}
function handleAwaitingName(text, replyToken, userId) {
  if (text === FALLBACK_RETRY_TEXT) { sendLineReply(replyToken, 'お名前を入力してください。'); return; }
  var trimmed = text.trim();
  if (!trimmed || trimmed.length > 100) { sendFallbackWithContact(replyToken, 'お名前を入力してください。\n（100文字以内でご入力ください）'); return; }
  var tempData = getUserState(userId).context; tempData.patient_name = trimmed;
  setUserState(userId, USER_STATES.AWAITING_PHONE, tempData); sendLineReply(replyToken, 'お名前を確認しました。\n\n電話番号を入力してください（例: 09012345678）。');
}
function handleAwaitingPhone(text, replyToken, userId) {
  if (text === FALLBACK_RETRY_TEXT) { sendLineReply(replyToken, '電話番号を入力してください（例: 09012345678）。'); return; }
  var tempData = getUserState(userId).context;
  var normalized = normalizePhoneInput(text);
  if (!validatePhoneNumber(normalized)) { sendFallbackWithContact(replyToken, '電話番号の形式が正しくありません。もう一度入力してください（例: 09012345678 または 090-1234-5678）。'); return; }
  tempData.phone = normalized; setUserState(userId, USER_STATES.AWAITING_DATE, tempData); sendDatePromptWithQuickReply(replyToken, userId);
}
function sendDatePromptWithQuickReply(replyToken, userId) {
  var dateOptions = [{ label: '今日', text: '今日' }, { label: '明日', text: '明日' }, { label: '明後日', text: '明後日' }, { label: '来週月曜', text: '来週月曜' }, { label: '来週火曜', text: '来週火曜' }, { label: '来週水曜', text: '来週水曜' }, { label: '来週木曜', text: '来週木曜' }, { label: '来週金曜', text: '来週金曜' }, { label: '来週土曜', text: '来週土曜' }, { label: '来週日曜', text: '来週日曜' }];
  sendQuickReply(replyToken, '希望日を入力してください（例: 今日、明日、来週月曜、または 2026-02-20）。下のボタンから選ぶか、日付を入力してください。', dateOptions);
}
function handleAwaitingDate(text, replyToken, userId) {
  if (text === FALLBACK_RETRY_TEXT) { sendDatePromptWithQuickReply(replyToken, userId); return; }
  var tempData = getUserState(userId).context;
  var parsedDate = parseDateInput(text);
  if (!parsedDate) { sendFallbackWithContact(replyToken, '日付の形式が正しくありません。もう一度入力してください（例: 今日、明日、来週月曜、または 2026-02-20）。'); return; }
  tempData.reserved_date = parsedDate; setUserState(userId, USER_STATES.AWAITING_TIME, tempData); sendTimePromptWithQuickReply(replyToken);
}
function sendTimePromptWithQuickReply(replyToken) {
  var timeOptions = ['9:00', '9:30', '10:00', '10:30', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00'].map(function(t) { return { label: t, text: t }; });
  sendQuickReply(replyToken, '希望時間を入力してください（例: 10:00 または 10時）。下のボタンから選ぶか、時刻を入力してください。', timeOptions);
}
function handleAwaitingTime(text, replyToken, userId) {
  if (text === FALLBACK_RETRY_TEXT) { sendTimePromptWithQuickReply(replyToken); return; }
  var tempData = getUserState(userId).context;
  var normalized = normalizeTimeInput(text);
  if (!validateTime(normalized)) { sendFallbackWithContact(replyToken, '時間の形式が正しくありません。もう一度入力してください（例: 10:00 または 10時）。'); return; }
  tempData.reserved_start = normalized; tempData.reserved_end = calculateEndTime(normalized);
  setUserState(userId, USER_STATES.AWAITING_TREATMENT, tempData);
  var menuOptions = ['初診（30分）', '再診（30分）', '再診（60分）']; sendQuickReply(replyToken, '施術の種類を選択してください。', menuOptions.map(function(opt) { return { label: opt, text: opt }; }));
}
function handleAwaitingTreatment(text, replyToken, userId) {
  var tempData = getUserState(userId).context; tempData.menu_type = text; tempData.visit_type = text.indexOf('初診') >= 0 ? VISIT_TYPE.FIRST : VISIT_TYPE.REPEAT;
  var profile = getLineProfile(userId); if (profile) tempData.line_display_name = profile.userId;
  var result = createReservation(tempData);
  var paymentLink = null; try { paymentLink = createPaymentLink(result.id, tempData.patient_name, getDepositAmount()); } catch (e) { Logger.log('createPaymentLink error: ' + e.message); }
  if (paymentLink) {
    setUserState(userId, USER_STATES.AWAITING_PAYMENT, { reservation_id: result.id, payment_link: paymentLink });
    sendLineReply(replyToken, MessageTemplates.getDepositRequestMessage(result.id, tempData.reserved_date, tempData.reserved_start, tempData.menu_type, paymentLink));
  } else { sendLineReply(replyToken, '決済リンクの作成に失敗しました。管理者にお問い合わせください。'); clearUserState(userId); }
}
function handleAwaitingPayment(text, replyToken, userId) {
  var tempData = getUserState(userId).context; var reservationId = tempData.reservation_id; var storedLink = tempData.payment_link;
  var reservation = getReservationById(reservationId);
  if (reservation && reservation.deposit_status === DEPOSIT_STATUS.PAID) { sendLineReply(replyToken, 'お支払いが確認されました。予約が確定しました！'); clearUserState(userId); }
  else if (storedLink) { sendLineReply(replyToken, 'お支払いがまだ完了していません。\n\n下のリンクからデポジットをお支払いください。\n\n' + storedLink + '\n\nお支払い完了後、「支払完了」と返信してください。'); }
  else { sendLineReply(replyToken, 'デポジットのお支払いがまだです。\n\n支払いリンクが届いていない場合は、管理者にお問い合わせください。'); }
}
function handleChangeFlow(replyToken, userId) { sendLineReply(replyToken, '予約変更機能は準備中です。管理者にお問い合わせください。'); }
function handleCancelFlow(replyToken, userId) { sendLineReply(replyToken, 'キャンセル機能は準備中です。管理者にお問い合わせください。'); }
function handleWaitlistFlow(replyToken, userId) { sendLineReply(replyToken, '待機リスト登録機能は準備中です。'); }
function handleFollow(userId) { var profile = getLineProfile(userId); var displayName = profile ? profile.displayName : '患者さん'; Logger.log('User followed: ' + userId); var message = MessageTemplates.getWelcomeMessage(); sendLinePush(userId, typeof message === 'string' ? message : message.text); }
function handleUnfollow(userId) { Logger.log('User unfollowed: ' + userId); clearUserState(userId); }
function setUserState(userId, state, context) { PropertiesService.getUserProperties().setProperty(TEMP_DATA_KEY_PREFIX + userId, JSON.stringify({ state: state, context: context || {}, timestamp: Date.now() })); }
function getUserState(userId) {
  var data = PropertiesService.getUserProperties().getProperty(TEMP_DATA_KEY_PREFIX + userId);
  if (!data) return { state: USER_STATES.IDLE, context: {} };
  var parsed = JSON.parse(data); if (Date.now() - parsed.timestamp > 24 * 60 * 60 * 1000) { clearUserState(userId); return { state: USER_STATES.IDLE, context: {} }; }
  return parsed;
}
function clearUserState(userId) { PropertiesService.getUserProperties().deleteProperty(TEMP_DATA_KEY_PREFIX + userId); }
function parseDateInput(text) {
  if (!text || typeof text !== 'string') return null;
  var s = text.trim();
  var patterns = [/(\d{4})-(\d{1,2})-(\d{1,2})/, /(\d{1,2})\/(\d{1,2})\/(\d{4})/, /(\d{4})\/(\d{1,2})\/(\d{1,2})/];
  for (var i = 0; i < patterns.length; i++) { var match = s.match(patterns[i]); if (match) return match[0].indexOf('-') !== -1 ? match[0] : formatDateFromMatch(match, patterns[i]); }
  var tz = 'Asia/Tokyo'; var now = new Date(); var todayStr = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
  if (s === '今日') return todayStr;
  if (s === '明日' || s === '翌日') return addDaysToDateStr(todayStr, 1);
  if (s === '明後日') return addDaysToDateStr(todayStr, 2);
  var weekdays = { '月': 1, '火': 2, '水': 3, '木': 4, '金': 5, '土': 6, '日': 7 };
  var nextWeekMatch = s.match(/^来週([月火水木金土日])曜?/);
  if (nextWeekMatch) { var targetDow = weekdays[nextWeekMatch[1]]; var d = getNextWeekday(now, targetDow, tz); return d ? Utilities.formatDate(d, tz, 'yyyy-MM-dd') : null; }
  var thisWeekMatch = s.match(/^(今週|今週の)?([月火水木金土日])曜?/);
  if (thisWeekMatch) { var targetDow2 = weekdays[thisWeekMatch[2]]; var d2 = getThisOrNextWeekday(now, targetDow2, tz); return d2 ? Utilities.formatDate(d2, tz, 'yyyy-MM-dd') : null; }
  return null;
}
function formatDateFromMatch(match, pattern) {
  var str = match[0]; if (str.indexOf('-') !== -1 && str.length >= 10) return str;
  var parts = str.split('/'); if (parts.length !== 3) return str;
  var y, m, d; if (parts[0].length === 4) { y = parts[0]; m = parts[1].length === 1 ? '0' + parts[1] : parts[1]; d = parts[2].length === 1 ? '0' + parts[2] : parts[2]; } else { y = parts[2]; m = parts[0].length === 1 ? '0' + parts[0] : parts[0]; d = parts[1].length === 1 ? '0' + parts[1] : parts[1]; }
  return y + '-' + m + '-' + d;
}
function addDaysToDateStr(dateStr, days) { var d = new Date(dateStr + 'T12:00:00+09:00'); d.setDate(d.getDate() + days); return Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy-MM-dd'); }
function getNextWeekday(now, targetDow, tz) {
  var todayStr = Utilities.formatDate(now, tz, 'yyyy-MM-dd'); var todayDate = new Date(todayStr + 'T12:00:00+09:00');
  var day = todayDate.getDay(); var currentDow = day === 0 ? 7 : day; var daysAhead = (targetDow - currentDow + 7) % 7; if (daysAhead === 0) daysAhead = 7;
  var d = new Date(todayDate); d.setDate(d.getDate() + daysAhead); return d;
}
function getThisOrNextWeekday(now, targetDow, tz) {
  var todayStr = Utilities.formatDate(now, tz, 'yyyy-MM-dd'); var todayDate = new Date(todayStr + 'T12:00:00+09:00');
  var day = todayDate.getDay(); var currentDow = day === 0 ? 7 : day; var daysAhead = (targetDow - currentDow + 7) % 7;
  var d = new Date(todayDate); d.setDate(d.getDate() + daysAhead); return d;
}

// ========== handlers/StripeWebhookHandler.gs ==========
function handlePaymentSuccess(paymentIntent) {
  var reservationId = paymentIntent.metadata ? paymentIntent.metadata.reservation_id : null;
  if (!reservationId) { Logger.log('No reservation_id in payment intent metadata'); return; }
  Logger.log('Processing payment success for reservation: ' + reservationId);
  var reservation = getReservationById(reservationId);
  if (!reservation) { Logger.log('Reservation not found: ' + reservationId); return; }
  updateReservation(reservationId, { deposit_status: DEPOSIT_STATUS.PAID, status: RESERVATION_STATUS.CONFIRMED });
  var confirmationMessage = MessageTemplates.getConfirmationMessage(reservation);
  sendLinePush(reservation.line_display_name, confirmationMessage);
  var adminUserId = getLineAdminUserId();
  if (adminUserId) {
    var adminMessage = '新しい予約が確定しました。\n\nID: ' + reservationId + '\n患者: ' + reservation.patient_name + '\n電話: ' + reservation.phone + '\n日時: ' + reservation.reserved_date + ' ' + reservation.reserved_start;
    sendLinePush(adminUserId, adminMessage);
  }
  Logger.log('Reservation confirmed: ' + reservationId);
}
function handlePaymentFailure(paymentIntent) {
  var reservationId = paymentIntent.metadata ? paymentIntent.metadata.reservation_id : null;
  var errorMessage = paymentIntent.last_payment_error ? paymentIntent.last_payment_error.message : 'Unknown error';
  if (!reservationId) { Logger.log('No reservation_id in payment intent metadata'); return; }
  Logger.log('Processing payment failure for reservation: ' + reservationId);
  var reservation = getReservationById(reservationId);
  if (!reservation) { Logger.log('Reservation not found: ' + reservationId); return; }
  updateReservation(reservationId, { deposit_status: DEPOSIT_STATUS.UNPAID });
  sendLinePush(reservation.line_display_name, MessageTemplates.getPaymentFailedMessage(errorMessage));
  Logger.log('Payment failed for reservation: ' + reservationId);
}
function handleRefund(charge) {
  var paymentIntentId = charge.payment_intent;
  if (!paymentIntentId) { Logger.log('No payment_intent_id in charge'); return; }
  Logger.log('Processing refund for payment intent: ' + paymentIntentId);
  var sheet = getReservationsSheet();
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    var reservation = data[i];
    var reservationId = reservation[0];
    var depositStatus = reservation[13];
    if (depositStatus === DEPOSIT_STATUS.PAID && reservation[10] === RESERVATION_STATUS.CANCELLED) {
      updateReservation(reservationId, { deposit_status: DEPOSIT_STATUS.REFUNDED });
      var lineDisplayName = reservation[4];
      var refundMessage = MessageTemplates.getRefundConfirmationMessage(reservationId);
      sendLinePush(lineDisplayName, refundMessage);
      Logger.log('Refund processed for reservation: ' + reservationId);
      break;
    }
  }
}

// ========== Setup.gs ==========
function runSetup() {
  Logger.log('=== Starting System Setup ===');
  initializeDefaultProperties(); createAllSheets(); createDashboardSheet(); createWaitlistDashboard(); setupTriggers();
  var validation = validateRequiredProperties(); if (!validation.valid) Logger.log('WARNING: Missing properties: ' + validation.missing.join(', '));
  Logger.log('=== Setup Complete ===');
}
function createAllSheets() {
  var ss = SpreadsheetApp.openById(getSpreadsheetId()); var sheetNames = [SHEET_NAMES.RESERVATIONS, SHEET_NAMES.WAITLIST, SHEET_NAMES.WEEKLY_SUMMARY];
  for (var i = 0; i < sheetNames.length; i++) {
    var sheet = ss.getSheetByName(sheetNames[i]);
    if (!sheet) { if (sheetNames[i] === SHEET_NAMES.RESERVATIONS) sheet = createSheetWithHeaders(ss, SHEET_NAMES.RESERVATIONS, RESERVATIONS_HEADERS); else if (sheetNames[i] === SHEET_NAMES.WAITLIST) sheet = createSheetWithHeaders(ss, SHEET_NAMES.WAITLIST, WAITLIST_HEADERS); else if (sheetNames[i] === SHEET_NAMES.WEEKLY_SUMMARY) sheet = createSheetWithHeaders(ss, SHEET_NAMES.WEEKLY_SUMMARY, WEEKLY_SUMMARY_HEADERS); Logger.log('Created sheet: ' + sheetNames[i]); }
  }
}
function setupTriggers() {
  deleteExistingTriggers();
  ScriptApp.newTrigger('sendDayBeforeReminders').timeBased().everyDays(1).atHour(8).create();
  var checkTimes = [9, 10, 11, 12, 13, 14, 15, 16, 17]; for (var i = 0; i < checkTimes.length; i++) ScriptApp.newTrigger('checkForNoShows').timeBased().everyDays(1).atHour(checkTimes[i]).create();
  ScriptApp.newTrigger('cleanupWaitlist').timeBased().everyDays(1).atHour(22).create();
  ScriptApp.newTrigger('generateWeeklyReport').timeBased().onWeekDay(ScriptApp.WeekDay.SUNDAY).atHour(22).create();
  ScriptApp.newTrigger('updateDashboard').timeBased().everyDays(1).atHour(8).create();
}
function deleteExistingTriggers() { var triggers = ScriptApp.getProjectTriggers(); for (var i = 0; i < triggers.length; i++) ScriptApp.deleteTrigger(triggers[i]); }
function getSystemStatus() { var validation = validateRequiredProperties(); var triggers = ScriptApp.getProjectTriggers(); var status = { properties_configured: validation.valid, missing_properties: validation.missing, triggers_count: triggers.length, spreadsheets_accessible: false }; try { status.spreadsheets_accessible = (getReservationsSheet() !== null); } catch (e) {} return status; }
function healthCheck() { var status = getSystemStatus(); Logger.log('Properties: ' + (status.properties_configured ? 'OK' : 'MISSING')); Logger.log('Triggers: ' + status.triggers_count); Logger.log('Sheets: ' + (status.spreadsheets_accessible ? 'OK' : 'NG')); return status.properties_configured && status.spreadsheets_accessible; }
function clearUserStates() { var userProps = PropertiesService.getUserProperties(); var keys = userProps.getKeys(); var n = 0; for (var i = 0; i < keys.length; i++) { if (keys[i].indexOf(TEMP_DATA_KEY_PREFIX) === 0) { userProps.deleteProperty(keys[i]); n++; } } Logger.log('Cleared ' + n + ' user states'); }

// ========== KPIService.gs ==========
function calculateWeeklyKPIs(weekStart) {
  var sheet = getReservationsSheet(); var data = sheet.getDataRange().getValues(); var weekEnd = addDays(parseDate(weekStart), 6);
  var stats = { total_reservations: 0, total_no_shows: 0, same_day_cancellations: 0, resale_notifications: 0, resale_success_count: 0, total_deposits: 0, forfeited_deposits: 0 };
  for (var i = 1; i < data.length; i++) {
    var r = data[i]; var reservedDate = parseDate(r[7]); if (!reservedDate || reservedDate < parseDate(weekStart) || reservedDate > weekEnd) continue;
    if (r[10] !== RESERVATION_STATUS.PENDING) stats.total_reservations++; if (r[10] === RESERVATION_STATUS.NO_SHOW) stats.total_no_shows++;
    if (r[10] === RESERVATION_STATUS.CANCELLED && r[16]) { var hoursUntil = (new Date(r[7] + 'T' + r[8]) - new Date(r[16])) / (1000 * 60 * 60); if (hoursUntil < 24) stats.same_day_cancellations++; }
    if (r[17] === 'Y') stats.resale_notifications++; if (r[18] === 'Y') stats.resale_success_count++;
  }
  var noShowRate = stats.total_reservations > 0 ? ((stats.total_no_shows / stats.total_reservations) * 100).toFixed(2) : '0.00';
  var resaleRate = stats.same_day_cancellations > 0 ? ((stats.resale_success_count / stats.same_day_cancellations) * 100).toFixed(2) : '0.00';
  return { week_start: weekStart, total_reservations: stats.total_reservations, total_no_shows: stats.total_no_shows, no_show_rate: noShowRate, same_day_cancellations: stats.same_day_cancellations, resale_notifications: stats.resale_notifications, resale_success_count: stats.resale_success_count, resale_rate: resaleRate, total_deposits: stats.total_deposits, forfeited_deposits: stats.forfeited_deposits, estimated_recovered_revenue: stats.resale_success_count * getAverageUnitPrice() };
}
function saveWeeklySummary(kpiData) { var sheet = getWeeklySummarySheet(); sheet.appendRow([kpiData.week_start, kpiData.total_reservations, kpiData.total_no_shows, kpiData.no_show_rate, kpiData.same_day_cancellations, kpiData.resale_notifications, kpiData.resale_success_count, kpiData.estimated_recovered_revenue]); }
function generateWeeklyReport() { var now = new Date(); var weekStart = formatDate(getWeekStart(now)); var kpiData = calculateWeeklyKPIs(weekStart); saveWeeklySummary(kpiData); var adminUserId = getLineAdminUserId(); if (adminUserId) sendLinePush(adminUserId, MessageTemplates.getWeeklySummaryMessage(kpiData)); }
function getCurrentWeekKPIs() { var now = new Date(); return calculateWeeklyKPIs(formatDate(getWeekStart(now))); }
function compareKPIsToTargets(kpiData) {
  return { no_show_rate: { actual: parseFloat(kpiData.no_show_rate), target: 5.0, achieved: parseFloat(kpiData.no_show_rate) <= 5.0 }, resale_rate: { actual: parseFloat(kpiData.resale_rate), target: 20.0, achieved: parseFloat(kpiData.resale_rate) >= 20.0 } };
}

// ========== Dashboard.gs ==========
function createDashboardSheet() {
  var ss = SpreadsheetApp.openById(getSpreadsheetId()); var existingSheet = ss.getSheetByName('Dashboard'); if (existingSheet) ss.deleteSheet(existingSheet); var sheet = ss.insertSheet('Dashboard');
  sheet.getRange(1, 1).setValue('予約管理システム - ダッシュボード').setFontWeight('bold').setFontSize(18);
  var currentKPIs = getCurrentWeekKPIs(); var targets = compareKPIsToTargets(currentKPIs);
  var summaryData = [['', '今週', '前週', '変化'], ['総予約件数', currentKPIs.total_reservations, '-', '-'], ['無断件数', currentKPIs.total_no_shows, '-', '-'], ['無断率', currentKPIs.no_show_rate + '%', '-', '-'], ['当日キャンセル', currentKPIs.same_day_cancellations, '-', '-'], ['再販通知回数', currentKPIs.resale_notifications, '-', '-'], ['再販成功数', currentKPIs.resale_success_count, '-', '-'], ['推定回収額', currentKPIs.estimated_recovered_revenue + '円', '-', '-']];
  sheet.getRange(4, 1, 11, 4).setValues(summaryData);
  sheet.getRange(13, 1).setValue('【KPI目標達成状況】').setFontWeight('bold').setFontSize(14);
  var targetData = [['', '目標', '実績', '達成'], ['無断率', targets.no_show_rate.target + '%', targets.no_show_rate.actual + '%', targets.no_show_rate.achieved ? '✓' : '✗'], ['再販率', targets.resale_rate.target + '%', targets.resale_rate.actual + '%', targets.resale_rate.achieved ? '✓' : '✗']];
  sheet.getRange(14, 1, 16, 4).setValues(targetData); sheet.getRange(20, 1).setValue('最終更新: ' + formatDateTime(new Date())).setFontStyle('italic').setFontSize(10);
}
function updateDashboard() { var ss = SpreadsheetApp.openById(getSpreadsheetId()); var sheet = ss.getSheetByName('Dashboard'); if (!sheet) { createDashboardSheet(); return; } var currentKPIs = getCurrentWeekKPIs(); sheet.getRange(5, 2, 11, 2).setValues([[currentKPIs.total_reservations], [currentKPIs.total_no_shows], [currentKPIs.no_show_rate + '%'], [currentKPIs.same_day_cancellations], [currentKPIs.resale_notifications], [currentKPIs.resale_success_count], [currentKPIs.estimated_recovered_revenue + '円']]); var targets = compareKPIsToTargets(currentKPIs); sheet.getRange(15, 3).setValue(targets.no_show_rate.actual + '%'); sheet.getRange(15, 4).setValue(targets.no_show_rate.achieved ? '✓' : '✗'); sheet.getRange(16, 3).setValue(targets.resale_rate.actual + '%'); sheet.getRange(16, 4).setValue(targets.resale_rate.achieved ? '✓' : '✗'); sheet.getRange(20, 1).setValue('最終更新: ' + formatDateTime(new Date())); }
function createWaitlistDashboard() {
  var ss = SpreadsheetApp.openById(getSpreadsheetId()); var existingSheet = ss.getSheetByName('Waitlist Dashboard'); if (existingSheet) ss.deleteSheet(existingSheet); var sheet = ss.insertSheet('Waitlist Dashboard');
  sheet.getRange(1, 1).setValue('待機リスト - ダッシュボード').setFontWeight('bold').setFontSize(18);
  var waitlistEntries = getWaitlistReservations(); var totalCount = waitlistEntries.length; var sameDayOkCount = waitlistEntries.filter(function(e) { return e.same_day_ok === 'Y'; }).length;
  sheet.getRange(3, 1).setValue('【待機リストサマリー】').setFontWeight('bold').setFontSize(14); sheet.getRange(4, 1).setValue('総登録数'); sheet.getRange(4, 2).setValue(totalCount + '人'); sheet.getRange(5, 1).setValue('当日OK'); sheet.getRange(5, 2).setValue(sameDayOkCount + '人');
  if (totalCount > 0) { var rows = [['ID', '電話', '希望時間', '当日OK', '最終通知']]; for (var i = 0; i < Math.min(waitlistEntries.length, 20); i++) rows.push([waitlistEntries[i].id, waitlistEntries[i].phone, waitlistEntries[i].preferred_time, waitlistEntries[i].same_day_ok === 'Y' ? '可' : '不可', waitlistEntries[i].last_notified_at || 'なし']); sheet.getRange(8, 1, 7 + rows.length, 5).setValues(rows); } else sheet.getRange(8, 1).setValue('登録者なし');
}

// ========== tests/TestSuite.gs ==========
function runAllTests() { Logger.log('=== Starting Unit Tests ==='); var results = { total: 0, passed: 0, failed: 0, tests: [] }; results.tests = testValidationUtils().concat(testDateUtils()); for (var i = 0; i < results.tests.length; i++) { results.total++; if (results.tests[i].passed) results.passed++; else results.failed++; } Logger.log('Total: ' + results.total + ' Passed: ' + results.passed + ' Failed: ' + results.failed); return results; }
function testValidationUtils() { return [{ name: 'Valid Phone', passed: validatePhoneNumber('09012345678'), message: 'OK' }, { name: 'Invalid Phone', passed: !validatePhoneNumber('123'), message: 'OK' }, { name: 'Valid Date', passed: validateDate('2026-02-20'), message: 'OK' }, { name: 'Valid Time', passed: validateTime('10:30'), message: 'OK' }]; }
function testDateUtils() { var t = []; try { var f = formatDate(new Date('2026-02-20')); t.push({ name: 'Format Date', passed: f === '2026-02-20', message: f }); } catch (e) { t.push({ name: 'Format Date', passed: false, message: e.toString() }); } try { var a = formatDate(addDays(new Date('2026-02-20'), 7)); t.push({ name: 'Add Days', passed: a === '2026-02-27', message: a }); } catch (e) { t.push({ name: 'Add Days', passed: false, message: e.toString() }); } return t; }
