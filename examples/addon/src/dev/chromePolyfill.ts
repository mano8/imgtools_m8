// src/dev/chromePolyfill.ts
function createLocalStorageBackend() {
    const defaultValues = {
        jwt: "test-jwt",
        jwt_expires: Date.now() + 3600000, // 1 hour from now
        session_id: "test-session",
        user_name: "Console User",
      };
    
      // Initialize localStorage if keys are missing
      for (const [key, value] of Object.entries(defaultValues)) {
        if (localStorage.getItem(key) === null) {
          localStorage.setItem(key, JSON.stringify(value));
        }
      }
  return {
    get(
      keys: string | string[] | Record<string, any>,
      cb: (items: Record<string, any>) => void
    ) {
      const result: Record<string, any> = {};
      if (Array.isArray(keys)) {
        keys.forEach((k) => {
          const v = localStorage.getItem(k);
          result[k] = v != null ? JSON.parse(v) : undefined;
        });
      } else if (typeof keys === "string") {
        const v = localStorage.getItem(keys);
        result[keys] = v != null ? JSON.parse(v) : undefined;
      } else {
        for (const k in keys) {
          const v = localStorage.getItem(k);
          result[k] = v != null ? JSON.parse(v) : keys[k];
        }
      }
      cb(result);
    },
    set(items: Record<string, any>, cb?: () => void) {
      for (const [k, v] of Object.entries(items)) {
        localStorage.setItem(k, JSON.stringify(v));
      }
      cb?.();
    },
    remove(keys: string | string[], cb?: () => void) {
      if (Array.isArray(keys)) {
        keys.forEach((k) => localStorage.removeItem(k));
      } else {
        localStorage.removeItem(keys);
      }
      cb?.();
    },
  };
}

// Fake runtime messaging
const listeners: Array<
  (msg: any, sender: any, sendResponse: (resp?: any) => void) => void
> = [];

function fakeSendMessage(
  message: any,
  responseCallback?: (response: any) => void
) {
  console.log("[DEV] chrome.runtime.sendMessage called:", message);

  // Call the listeners and simulate async response
  for (const listener of listeners) {
    listener(message, { id: "fake-sender-dev" }, (response) => {
      responseCallback?.(response);
    });
  }
}

function fakeOnMessage() {
  return {
    addListener: (cb: (typeof listeners)[0]) => {
      listeners.push(cb);
    },
    removeListener: (cb: (typeof listeners)[0]) => {
      const i = listeners.indexOf(cb);
      if (i !== -1) listeners.splice(i, 1);
    },
  };
}

// Attach to window.chrome
(window as any).chrome = (window as any).chrome || {};
chrome.storage = chrome.storage || {};
chrome.storage.local = createLocalStorageBackend();

const changeListeners: Array<
  (changes: Record<string, any>, areaName: string) => void
> = [];

chrome.storage.onChanged = {
  addListener(cb: (typeof changeListeners)[0]) {
    changeListeners.push(cb);
  },
  removeListener(cb: (typeof changeListeners)[0]) {
    const index = changeListeners.indexOf(cb);
    if (index !== -1) changeListeners.splice(index, 1);
  },
};

// Patch set to fire change events
const originalSet = chrome.storage.local.set;
chrome.storage.local.set = (items, cb) => {
  const changes: Record<string, any> = {};

  for (const [key, newValue] of Object.entries(items)) {
    const oldRaw = localStorage.getItem(key);
    const oldValue = oldRaw != null ? JSON.parse(oldRaw) : undefined;
    if (JSON.stringify(oldValue) !== JSON.stringify(newValue)) {
      changes[key] = {
        oldValue,
        newValue,
      };
    }
  }

  originalSet(items, () => {
    for (const listener of changeListeners) {
      listener(changes, "local");
    }
    cb?.();
  });
};

chrome.runtime = chrome.runtime || {};
chrome.runtime.sendMessage = chrome.runtime.sendMessage || fakeSendMessage;
chrome.runtime.onMessage = chrome.runtime.onMessage || fakeOnMessage();
chrome.runtime.onMessageExternal =
  chrome.runtime.onMessageExternal || fakeOnMessage();
