// ZargoBot - Google Apps Script API
// Bot Sheet'ga ma'lumot yozadi va o'qiydi shu kod orqali

const SHEET_PRODUCTS = 'Маҳсулотлар';
const SHEET_CUSTOMERS = 'Мижозлар Малумотлари';
const SHEET_ORDERS = 'Буюртмалар';
const SHEET_NIGHT_ORDERS = 'Тунги_буюртмалар';

// === GET so'rovlarini qabul qilish (o'qish) ===
function doGet(e) {
  try {
    const action = e.parameter.action;
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    let result;
    switch (action) {
      case 'products':         result = getProducts(ss); break;
      case 'customer':         result = getCustomer(ss, e.parameter.phone); break;
      case 'customers':        result = getAllCustomers(ss); break;
      case 'orders':           result = getAllOrders(ss); break;
      case 'customer_orders':  result = getCustomerOrders(ss, e.parameter.phone); break;
      case 'order_count':      result = getOrderCount(ss); break;
      case 'night_orders':     result = getNightOrders(ss); break;
      case 'ping':             result = { status: 'ok', time: new Date().toISOString() }; break;
      default:                 result = { error: 'Unknown action: ' + action };
    }
    return jsonResponse(result);
  } catch (err) {
    return jsonResponse({ error: err.toString() });
  }
}

// === POST so'rovlarini qabul qilish (yozish) ===
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const action = data.action;
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    let result;
    switch (action) {
      case 'save_customer':       result = saveCustomer(ss, data.customer); break;
      case 'update_customer':     result = updateCustomer(ss, data.phone, data.updates); break;
      case 'save_order':          result = saveOrder(ss, data.order); break;
      case 'save_night_order':    result = saveNightOrder(ss, data.order); break;
      case 'confirm_night_order': result = confirmNightOrder(ss, data.phone); break;
      case 'set_reminder':        result = updateCustomer(ss, data.phone, { reminders: data.value }); break;
      default:                    result = { error: 'Unknown action: ' + action };
    }
    return jsonResponse(result);
  } catch (err) {
    return jsonResponse({ error: err.toString() });
  }
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// =========================================================================
// MAHSULOTLAR
// =========================================================================
function getProducts(ss) {
  const sheet = ss.getSheetByName(SHEET_PRODUCTS);
  const data = sheet.getDataRange().getValues();
  const products = [];
  for (let i = 1; i < data.length; i++) {
    if (!data[i][0]) continue;
    products.push({
      name:       data[i][0],
      somoni:     Number(data[i][1]) || 0,
      diram:      Number(data[i][2]) || 0,
      category:   data[i][3] || '',
      splittable: data[i][4] || 'Йўқ'  // Йўқ / Дона / Грамм
    });
  }
  return { products: products };
}

// =========================================================================
// MIJOZLAR
// =========================================================================
function getCustomer(ss, phone) {
  const sheet = ss.getSheetByName(SHEET_CUSTOMERS);
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(phone)) {
      return { found: true, customer: rowToCustomer(data[i]) };
    }
  }
  return { found: false };
}

function getAllCustomers(ss) {
  const sheet = ss.getSheetByName(SHEET_CUSTOMERS);
  const data = sheet.getDataRange().getValues();
  const customers = [];
  for (let i = 1; i < data.length; i++) {
    if (!data[i][0]) continue;
    customers.push(rowToCustomer(data[i]));
  }
  return { customers: customers };
}

function rowToCustomer(row) {
  return {
    phone:         row[0],
    name:          row[1],
    gender:        row[2],
    first_order:   row[3],
    last_order:    row[4],
    total_orders:  Number(row[5]) || 0,
    total_spent:   Number(row[6]) || 0,
    address:       row[7],
    reminders:     row[8] !== 'off'
  };
}

function saveCustomer(ss, customer) {
  const sheet = ss.getSheetByName(SHEET_CUSTOMERS);
  const data = sheet.getDataRange().getValues();
  const today = new Date().toISOString().slice(0, 10);

  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(customer.phone)) {
      sheet.getRange(i + 1, 1, 1, 9).setValues([[
        customer.phone,
        customer.name || data[i][1],
        customer.gender || data[i][2],
        data[i][3] || today,
        customer.last_order || today,
        customer.total_orders != null ? customer.total_orders : data[i][5],
        customer.total_spent != null ? customer.total_spent : data[i][6],
        customer.address || data[i][7],
        customer.reminders || data[i][8] || 'on'
      ]]);
      return { saved: true, action: 'updated' };
    }
  }

  sheet.appendRow([
    customer.phone,
    customer.name,
    customer.gender,
    today,
    today,
    customer.total_orders || 0,
    customer.total_spent || 0,
    customer.address || '',
    'on'
  ]);
  return { saved: true, action: 'created' };
}

function updateCustomer(ss, phone, updates) {
  const sheet = ss.getSheetByName(SHEET_CUSTOMERS);
  const data = sheet.getDataRange().getValues();
  const cols = ['phone', 'name', 'gender', 'first_order', 'last_order',
                'total_orders', 'total_spent', 'address', 'reminders'];

  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(phone)) {
      for (let key in updates) {
        const idx = cols.indexOf(key);
        if (idx >= 0) sheet.getRange(i + 1, idx + 1).setValue(updates[key]);
      }
      return { updated: true };
    }
  }
  return { updated: false, error: 'Mijoz topilmadi' };
}

// =========================================================================
// BUYURTMALAR
// =========================================================================
function getAllOrders(ss) {
  const sheet = ss.getSheetByName(SHEET_ORDERS);
  const data = sheet.getDataRange().getValues();
  const orders = [];
  for (let i = 1; i < data.length; i++) {
    if (!data[i][0]) continue;
    orders.push(rowToOrder(data[i]));
  }
  return { orders: orders };
}

function getCustomerOrders(ss, phone) {
  const all = getAllOrders(ss).orders;
  return { orders: all.filter(o => String(o.phone) === String(phone)) };
}

function rowToOrder(row) {
  return {
    number:  row[0],
    date:    row[1],
    phone:   row[2],
    name:    row[3],
    address: row[4],
    items:   row[5],
    total:   Number(row[6]) || 0,
    payment: row[7],
    status:  row[8]
  };
}

function getOrderCount(ss) {
  const sheet = ss.getSheetByName(SHEET_ORDERS);
  const data = sheet.getDataRange().getValues();
  let count = 0;
  for (let i = 1; i < data.length; i++) {
    if (data[i][0]) count++;
  }
  return { count: count };
}

function saveOrder(ss, order) {
  const sheet = ss.getSheetByName(SHEET_ORDERS);
  const newNumber = getOrderCount(ss).count + 1;
  sheet.appendRow([
    newNumber,
    order.date || new Date().toISOString(),
    order.phone,
    order.name,
    order.address,
    order.items,
    Number(order.total) || 0,
    order.payment || 'нақд',
    order.status || 'қабул қилинди'
  ]);
  return { saved: true, number: newNumber };
}

// =========================================================================
// TUNGI BUYURTMALAR
// =========================================================================
function getNightOrders(ss) {
  const sheet = ss.getSheetByName(SHEET_NIGHT_ORDERS);
  const data = sheet.getDataRange().getValues();
  const orders = [];
  for (let i = 1; i < data.length; i++) {
    if (!data[i][0]) continue;
    orders.push({
      row:        i + 1,
      date:       data[i][0],
      phone:      data[i][1],
      name:       data[i][2],
      address:    data[i][3],
      items:      data[i][4],
      total:      Number(data[i][5]) || 0,
      confirmed:  data[i][6]
    });
  }
  return { night_orders: orders };
}

function saveNightOrder(ss, order) {
  const sheet = ss.getSheetByName(SHEET_NIGHT_ORDERS);
  sheet.appendRow([
    order.date || new Date().toISOString(),
    order.phone,
    order.name,
    order.address,
    order.items,
    Number(order.total) || 0,
    'кутилмоқда'
  ]);
  return { saved: true };
}

function confirmNightOrder(ss, phone) {
  const sheet = ss.getSheetByName(SHEET_NIGHT_ORDERS);
  const data = sheet.getDataRange().getValues();
  for (let i = data.length - 1; i >= 1; i--) {
    if (String(data[i][1]) === String(phone) && data[i][6] === 'кутилмоқда') {
      sheet.getRange(i + 1, 7).setValue('тасдиқланди');
      return {
        confirmed: true,
        order: {
          date:    data[i][0],
          phone:   data[i][1],
          name:    data[i][2],
          address: data[i][3],
          items:   data[i][4],
          total:   Number(data[i][5]) || 0
        }
      };
    }
  }
  return { confirmed: false };
}
