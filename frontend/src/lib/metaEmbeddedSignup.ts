export type WhatsAppEmbeddedSignupSession = {
  type: "WA_EMBEDDED_SIGNUP";
  event: string;
  version?: number | string;
  data?: {
    waba_id?: string;
    phone_number_id?: string;
    [key: string]: unknown;
  };
};

type FacebookLoginResponse = {
  status?: string;
  authResponse?: {
    code?: string;
    [key: string]: unknown;
  };
};

type FacebookSdk = {
  init(options: {
    appId: string;
    cookie?: boolean;
    xfbml?: boolean;
    version: string;
  }): void;
  login(
    callback: (response: FacebookLoginResponse) => void,
    options: {
      config_id: string;
      response_type: "code";
      override_default_response_type: true;
      extras: {
        setup: Record<string, never>;
        featureType: string;
        sessionInfoVersion: string;
      };
    },
  ): void;
};

declare global {
  interface Window {
    FB?: FacebookSdk;
    fbAsyncInit?: () => void;
  }
}

let sdkPromise: Promise<void> | null = null;
let initializedAppId: string | null = null;

export function loadMetaFacebookSdk(appId: string, version: string) {
  if (window.FB && initializedAppId === appId) {
    return Promise.resolve();
  }
  if (sdkPromise) return sdkPromise;

  sdkPromise = new Promise<void>((resolve, reject) => {
    const initialize = () => {
      if (!window.FB) {
        reject(new Error("SDK da Meta não ficou disponível."));
        return;
      }
      window.FB.init({
        appId,
        cookie: true,
        xfbml: false,
        version,
      });
      initializedAppId = appId;
      resolve();
    };

    if (window.FB) {
      initialize();
      return;
    }

    window.fbAsyncInit = initialize;
    const existing = document.getElementById("meta-facebook-jssdk");
    if (existing) return;

    const script = document.createElement("script");
    script.id = "meta-facebook-jssdk";
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    script.src = "https://connect.facebook.net/pt_BR/sdk.js";
    script.onerror = () => reject(new Error("Não foi possível carregar o SDK da Meta."));
    document.head.appendChild(script);
  }).catch((error) => {
    sdkPromise = null;
    throw error;
  });

  return sdkPromise;
}

function isFacebookOrigin(origin: string) {
  try {
    const hostname = new URL(origin).hostname.toLowerCase();
    return hostname === "facebook.com" || hostname.endsWith(".facebook.com");
  } catch {
    return false;
  }
}

function parseSession(data: unknown): WhatsAppEmbeddedSignupSession | null {
  let parsed = data;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed) as unknown;
    } catch {
      return null;
    }
  }
  if (!parsed || typeof parsed !== "object") return null;
  const candidate = parsed as Partial<WhatsAppEmbeddedSignupSession>;
  if (candidate.type !== "WA_EMBEDDED_SIGNUP" || !candidate.event) return null;
  return candidate as WhatsAppEmbeddedSignupSession;
}

export function startWhatsAppCoexistenceSignup(options: {
  configId: string;
  featureType: string;
  timeoutMs?: number;
}) {
  if (!window.FB) {
    return Promise.reject(
      new Error("SDK da Meta ainda não está pronto. Aguarde alguns segundos e tente novamente."),
    );
  }

  const timeoutMs = options.timeoutMs ?? 180_000;
  return new Promise<{ code: string; session: WhatsAppEmbeddedSignupSession }>(
    (resolve, reject) => {
      let code: string | null = null;
      let session: WhatsAppEmbeddedSignupSession | null = null;
      let settled = false;

      const finish = () => {
        if (settled || !code || !session) return;
        settled = true;
        cleanup();
        resolve({ code, session });
      };

      const onMessage = (event: MessageEvent) => {
        if (!isFacebookOrigin(event.origin)) return;
        const next = parseSession(event.data);
        if (!next) return;

        if (next.event === "CANCEL") {
          settled = true;
          cleanup();
          reject(new Error("Conexão com o WhatsApp cancelada na Meta."));
          return;
        }
        if (next.event === "ERROR") {
          settled = true;
          cleanup();
          reject(new Error("A Meta informou um erro durante o Embedded Signup."));
          return;
        }
        if (next.event.startsWith("FINISH")) {
          session = next;
          finish();
        }
      };

      const timeout = window.setTimeout(() => {
        if (settled) return;
        settled = true;
        cleanup();
        reject(
          new Error(
            "O Embedded Signup demorou demais para concluir. Tente novamente sem fechar a janela da Meta.",
          ),
        );
      }, timeoutMs);

      const cleanup = () => {
        window.clearTimeout(timeout);
        window.removeEventListener("message", onMessage);
      };

      window.addEventListener("message", onMessage);

      window.FB?.login(
        (response) => {
          const authCode = response.authResponse?.code?.trim();
          if (!authCode) {
            if (!settled) {
              settled = true;
              cleanup();
              reject(
                new Error(
                  "A Meta não retornou o código de autorização do Embedded Signup.",
                ),
              );
            }
            return;
          }
          code = authCode;
          finish();
        },
        {
          config_id: options.configId,
          response_type: "code",
          override_default_response_type: true,
          extras: {
            setup: {},
            featureType: options.featureType,
            sessionInfoVersion: "3",
          },
        },
      );
    },
  );
}
