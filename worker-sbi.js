function hexToBytes(hex) {
  if (!hex || hex.length % 2 !== 0) {
    throw new Error("Invalid hex");
  }

  const bytes = new Uint8Array(hex.length / 2);

  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(
      hex.slice(i, i + 2),
      16
    );
  }

  return bytes;
}


async function verifyDiscordRequest(
  request,
  body,
  publicKeyHex
) {
  const signature =
    request.headers.get("X-Signature-Ed25519");

  const timestamp =
    request.headers.get("X-Signature-Timestamp");

  if (!signature || !timestamp) {
    return false;
  }

  const publicKey =
    await crypto.subtle.importKey(
      "raw",
      hexToBytes(publicKeyHex),
      { name: "Ed25519" },
      false,
      ["verify"]
    );

  const message =
    new TextEncoder().encode(
      timestamp + body
    );

  return await crypto.subtle.verify(
    "Ed25519",
    publicKey,
    hexToBytes(signature),
    message
  );
}


async function startGitHubAction(
  env,
  stockCode,
  channelId,
  mode,
  portfolioJson = "[]",
  realizedProfit = "0",
  sbiCapital = "0",
  sbiWatchlistJson = "[]"
) {
  const url =
    "https://api.github.com/repos/" +
    "jojozmm2-cloud/AI_stock/" +
    "actions/workflows/discord.yml/dispatches";

  const response = await fetch(
    url,
    {
      method: "POST",

      headers: {
        "Accept":
          "application/vnd.github+json",

        "Authorization":
          `Bearer ${env.GITHUB_ACTIONS_TOKEN}`,

        "X-GitHub-Api-Version":
          "2026-03-10",

        "User-Agent":
          "ai-stock-discord-worker",

        "Content-Type":
          "application/json"
      },

      body: JSON.stringify({
        ref: "main",

        inputs: {
          stock_code: stockCode,
          channel_id: channelId,
          mode: mode,
          portfolio_json: portfolioJson,
          realized_profit: String(realizedProfit),
          sbi_capital: String(sbiCapital),
          sbi_watchlist_json: sbiWatchlistJson
        }
      })
    }
  );

  if (!response.ok) {
    const errorText =
      await response.text();

    console.error(
      "GitHub Actions error:",
      response.status,
      errorText
    );

    throw new Error(
      `GitHub Actions: ${response.status}`
    );
  }

  console.log(
    "GitHub Actions started:",
    stockCode,
    mode
  );
}


export default {
  async fetch(request, env, ctx) {

    // ブラウザで開いた時
    if (request.method === "GET") {
      return new Response(
        "✅ AI Stock Discord Worker is running"
      );
    }

    if (request.method !== "POST") {
      return new Response(
        "Method Not Allowed",
        { status: 405 }
      );
    }

    const body =
      await request.text();

    const valid =
      await verifyDiscordRequest(
        request,
        body,
        env.DISCORD_PUBLIC_KEY
      );

    if (!valid) {
      return new Response(
        "Invalid request signature",
        { status: 401 }
      );
    }

    const interaction =
      JSON.parse(body);

    // DiscordのPING
    if (interaction.type === 1) {
      return Response.json({
        type: 1
      });
    }

    const command =
      interaction.data?.name;

    // /test
    if (command === "test") {
      return Response.json({
        type: 4,
        data: {
          content:
            "✅ AI Stock Tool がリクエストを受け取りました！"
        }
      });
    }

    // /sbi
    if (command === "sbi") {
      const subcommand =
        interaction.data?.options?.[0]?.name;

      const subcommandOptions =
        interaction.data?.options?.[0]?.options || [];

      await env.DB.prepare(
        `
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        `
      ).run();

      await env.DB.prepare(
        `
        CREATE TABLE IF NOT EXISTS sbi_watchlist (
          code TEXT PRIMARY KEY,
          take_profit REAL NOT NULL,
          stop_loss REAL NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        `
      ).run();

      await env.DB.prepare(
        `
        CREATE TABLE IF NOT EXISTS sbi_portfolio (
          code TEXT PRIMARY KEY,
          shares INTEGER NOT NULL,
          avg_price REAL NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        `
      ).run();

      await env.DB.prepare(
        `
        CREATE TABLE IF NOT EXISTS sbi_transactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT NOT NULL,
          type TEXT NOT NULL,
          shares INTEGER NOT NULL,
          price REAL NOT NULL,
          realized_profit REAL NOT NULL DEFAULT 0,
          estimated_tax REAL NOT NULL DEFAULT 0,
          net_profit REAL NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        `
      ).run();

      await env.DB.prepare(
        `
        CREATE TABLE IF NOT EXISTS sbi_pending_orders (
          code TEXT PRIMARY KEY,
          shares INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        `
      ).run();

      // /sbi 設定
      if (subcommand === "設定") {
        const capitalOption =
          subcommandOptions.find(
            option => option.name === "capital"
          );

        const capital =
          Math.floor(Number(capitalOption?.value));

        if (
          !Number.isFinite(capital) ||
          capital <= 0
        ) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ 運用資金は1円以上の数字で入力してください。",
              flags: 64
            }
          });
        }

        await env.DB.prepare(
          `
          INSERT INTO app_settings (
            key,
            value,
            updated_at
          )
          VALUES ('sbi_capital', ?, CURRENT_TIMESTAMP)
          ON CONFLICT(key)
          DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
          `
        )
          .bind(String(capital))
          .run();
      }

      const saved = await env.DB.prepare(
        `
        SELECT value
        FROM app_settings
        WHERE key = 'sbi_capital'
        `
      ).first();

      const capital =
        Number(saved?.value || 0);

      // /sbi 分析
      if (subcommand === "分析") {
        const codeOption =
          subcommandOptions.find(
            option => option.name === "code"
          );

        let stockCode =
          String(codeOption?.value || "")
            .trim()
            .toUpperCase();

        if (
          stockCode.length === 4 &&
          /^\d{4}$/.test(stockCode)
        ) {
          stockCode = stockCode + ".T";
        }

        if (!stockCode) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ 銘柄コードを入力してください。",
              flags: 64
            }
          });
        }

        if (!Number.isFinite(capital) || capital <= 0) {
          return Response.json({
            type: 4,
            data: {
              content:
                "⚠️ 先に `/sbi 設定 capital:70000` のように運用資金を設定してください。",
              flags: 64
            }
          });
        }

        const channelId = interaction.channel_id;

        if (!channelId) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ Discordチャンネルを取得できませんでした。",
              flags: 64
            }
          });
        }

        ctx.waitUntil(
          startGitHubAction(
            env,
            stockCode,
            channelId,
            "sbi_analysis",
            "[]",
            "0",
            String(capital)
          ).catch(error => {
            console.error(error);
          })
        );

        return Response.json({
          type: 4,
          data: {
            embeds: [
              {
                title: "⏳ SBI短期売買プランを計算中",
                description:
                  `**${stockCode}** の株価と値動きを確認しています。\n` +
                  "完了後、このチャンネルにプランを送信します。",
                color: 0xD6A11D
              }
            ]
          }
        });
      }

      // /sbi 候補
      if (subcommand === "候補") {
        if (!Number.isFinite(capital) || capital <= 0) {
          return Response.json({
            type: 4,
            data: {
              content:
                "⚠️ 先に `/sbi 設定 capital:70000` のように運用資金を設定してください。",
              flags: 64
            }
          });
        }

        const channelId = interaction.channel_id;
        if (!channelId) {
          return Response.json({
            type: 4,
            data: {
              content: "❌ Discordチャンネルを取得できませんでした。",
              flags: 64
            }
          });
        }

        ctx.waitUntil(
          startGitHubAction(
            env,
            "",
            channelId,
            "sbi_candidates",
            "[]",
            "0",
            String(capital)
          ).catch(error => console.error(error))
        );

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: "🔎 SBI短期売買候補を検索中",
              description:
                "値動き・RSI・出来高を確認しています。\n" +
                "完了後、このチャンネルに上位5銘柄を送信します。",
              color: 0xD6A11D
            }]
          }
        });
      }

      // /sbi 千円候補（テスト用）
      if (subcommand === "千円候補") {
        if (!Number.isFinite(capital) || capital <= 0) {
          return Response.json({
            type: 4,
            data: {
              content:
                "⚠️ 先に `/sbi 設定 capital:100000` のように運用資金を設定してください。",
              flags: 64
            }
          });
        }

        const channelId = interaction.channel_id;
        if (!channelId) {
          return Response.json({
            type: 4,
            data: {
              content: "❌ Discordチャンネルを取得できませんでした。",
              flags: 64
            }
          });
        }

        ctx.waitUntil(
          startGitHubAction(
            env,
            "",
            channelId,
            "sbi_candidates_under_1000",
            "[]",
            "0",
            String(capital)
          ).catch(error => console.error(error))
        );

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: "🧪 SBI 1,000円以下候補を検索中",
              description:
                "1株1,000円以下のテスト対象から、値動き・RSI・出来高を確認しています。\n" +
                "完了後、このチャンネルに上位5銘柄を送信します。",
              color: 0xD6A11D
            }]
          }
        });
      }

      // /sbi 監視追加
      if (subcommand === "監視追加") {
        const codeOption = subcommandOptions.find(
          option => option.name === "code"
        );
        const takeProfitOption = subcommandOptions.find(
          option => option.name === "take_profit"
        );
        const stopLossOption = subcommandOptions.find(
          option => option.name === "stop_loss"
        );

        let stockCode = String(codeOption?.value || "")
          .trim()
          .toUpperCase();
        if (stockCode.length === 4 && /^\d{4}$/.test(stockCode)) {
          stockCode += ".T";
        }

        const takeProfit = Number(takeProfitOption?.value);
        const stopLoss = Number(stopLossOption?.value);

        if (
          !stockCode ||
          !Number.isFinite(takeProfit) ||
          !Number.isFinite(stopLoss) ||
          takeProfit <= 0 ||
          stopLoss <= 0 ||
          stopLoss >= takeProfit
        ) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ 銘柄コードと価格を確認してください。損切り候補は利確候補より低く設定します。",
              flags: 64
            }
          });
        }

        await env.DB.prepare(
          `
          INSERT INTO sbi_watchlist (
            code, take_profit, stop_loss, updated_at
          )
          VALUES (?, ?, ?, CURRENT_TIMESTAMP)
          ON CONFLICT(code)
          DO UPDATE SET
            take_profit = excluded.take_profit,
            stop_loss = excluded.stop_loss,
            updated_at = CURRENT_TIMESTAMP
          `
        ).bind(stockCode, takeProfit, stopLoss).run();

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: `✅ SBI監視に追加｜${stockCode}`,
              color: 0x2E8B57,
              fields: [
                {
                  name: "🎯 利確候補",
                  value: `${takeProfit.toLocaleString("ja-JP")}円`,
                  inline: true
                },
                {
                  name: "🛑 損切り候補",
                  value: `${stopLoss.toLocaleString("ja-JP")}円`,
                  inline: true
                }
              ],
              footer: {
                text: "登録内容は /sbi 監視一覧 で確認できます"
              }
            }]
          }
        });
      }

      // /sbi 注文判断
      if (subcommand === "注文判断") {
        const codeOption = subcommandOptions.find(
          option => option.name === "code"
        );
        let stockCode = String(codeOption?.value || "")
          .trim()
          .toUpperCase();
        if (stockCode.length === 4 && /^\d{4}$/.test(stockCode)) {
          stockCode += ".T";
        }

        if (!stockCode) {
          return Response.json({
            type: 4,
            data: {
              content: "❌ 銘柄コードを入力してください。",
              flags: 64
            }
          });
        }
        if (!Number.isFinite(capital) || capital <= 0) {
          return Response.json({
            type: 4,
            data: {
              content:
                "⚠️ 先に `/sbi 設定 capital:70000` のように運用資金を設定してください。",
              flags: 64
            }
          });
        }

        const [holding, watch] = await Promise.all([
          env.DB.prepare(
            "SELECT code, shares, avg_price FROM sbi_portfolio WHERE code = ?"
          ).bind(stockCode).first(),
          env.DB.prepare(
            "SELECT code, take_profit, stop_loss FROM sbi_watchlist WHERE code = ?"
          ).bind(stockCode).first()
        ]);

        const channelId = interaction.channel_id;
        if (!channelId) {
          return Response.json({
            type: 4,
            data: {
              content: "❌ Discordチャンネルを取得できませんでした。",
              flags: 64
            }
          });
        }

        ctx.waitUntil(
          startGitHubAction(
            env,
            stockCode,
            channelId,
            "sbi_timing",
            JSON.stringify(holding ? [holding] : []),
            "0",
            String(capital),
            JSON.stringify(watch ? [watch] : [])
          ).catch(error => console.error(error))
        );

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: "⏱️ SBI注文タイミングを確認中",
              description:
                `**${stockCode}** の5分足・VWAP・日足を確認しています。\n` +
                "保有記録に応じて購入または売却判断を送信します。",
              color: 0xD6A11D
            }]
          }
        });
      }

      // /sbi 監視削除
      if (subcommand === "監視削除") {
        const codeOption = subcommandOptions.find(
          option => option.name === "code"
        );
        let stockCode = String(codeOption?.value || "")
          .trim()
          .toUpperCase();
        if (stockCode.length === 4 && /^\d{4}$/.test(stockCode)) {
          stockCode += ".T";
        }

        const current = await env.DB.prepare(
          "SELECT code FROM sbi_watchlist WHERE code = ?"
        ).bind(stockCode).first();

        if (!current) {
          return Response.json({
            type: 4,
            data: {
              content: `⚠️ **${stockCode}** は監視一覧にありません。`,
              flags: 64
            }
          });
        }

        await env.DB.prepare(
          "DELETE FROM sbi_watchlist WHERE code = ?"
        ).bind(stockCode).run();

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: `🗑️ SBI監視から削除｜${stockCode}`,
              description: "監視一覧から削除しました。売買履歴や保有記録には影響しません。",
              color: 0x6B7280
            }]
          }
        });
      }

      // /sbi 自動通知
      if (subcommand === "自動通知") {
        const enabledOption = subcommandOptions.find(
          option => option.name === "enabled"
        );
        const enabled = enabledOption?.value === true;
        const channelId = interaction.channel_id;

        if (enabled && !channelId) {
          return Response.json({
            type: 4,
            data: {
              content: "❌ Discordチャンネルを取得できませんでした。",
              flags: 64
            }
          });
        }

        const statements = [
          env.DB.prepare(
            `
            INSERT INTO app_settings (key, value, updated_at)
            VALUES ('sbi_auto_enabled', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            `
          ).bind(enabled ? "1" : "0")
        ];

        if (enabled) {
          statements.push(
            env.DB.prepare(
              `
              INSERT INTO app_settings (key, value, updated_at)
              VALUES ('sbi_alert_channel_id', ?, CURRENT_TIMESTAMP)
              ON CONFLICT(key)
              DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
              `
            ).bind(channelId)
          );
        }

        await env.DB.batch(statements);

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: enabled
                ? "🔔 SBI自動通知をオンにしました"
                : "🔕 SBI自動通知を停止しました",
              description: enabled
                ? "平日の10:00と13:30に、監視銘柄の注文判断をこのチャンネルへ送ります。"
                : "定時の注文判断通知は送信されません。手動の `/sbi 注文判断` は引き続き使えます。",
              color: enabled ? 0x2E8B57 : 0x6B7280,
              footer: {
                text: "監視銘柄がない場合はGitHub Actionsを起動しません"
              }
            }]
          }
        });
      }

      // /sbi 監視一覧
      if (subcommand === "監視一覧") {
        const result = await env.DB.prepare(
          `
          SELECT code, take_profit, stop_loss
          FROM sbi_watchlist
          ORDER BY updated_at DESC
          `
        ).run();
        const rows = result.results || [];

        if (rows.length === 0) {
          return Response.json({
            type: 4,
            data: {
              embeds: [{
                title: "👀 SBI監視一覧",
                description:
                  "まだ監視銘柄はありません。\n" +
                  "分析後に `/sbi 監視追加` で登録できます。",
                color: 0x6B7280
              }]
            }
          });
        }

        const channelId = interaction.channel_id;
        if (!channelId) {
          return Response.json({
            type: 4,
            data: {
              content: "❌ Discordチャンネルを取得できませんでした。",
              flags: 64
            }
          });
        }

        ctx.waitUntil(
          startGitHubAction(
            env,
            "",
            channelId,
            "sbi_watchlist",
            "[]",
            "0",
            String(capital),
            JSON.stringify(rows)
          ).catch(error => console.error(error))
        );

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: "⏳ SBI監視銘柄を確認中",
              description:
                `${rows.length}銘柄の現在価格を確認しています。\n` +
                "完了後、このチャンネルに結果を送信します。",
              color: 0xD6A11D
            }]
          }
        });
      }

      // /sbi 注文中
      if (subcommand === "注文中") {
        const codeOption =
          subcommandOptions.find(
            option => option.name === "code"
          );
        const sharesOption =
          subcommandOptions.find(
            option => option.name === "shares"
          );

        let stockCode =
          String(codeOption?.value || "")
            .trim()
            .toUpperCase();

        if (
          stockCode.length === 4 &&
          /^\d{4}$/.test(stockCode)
        ) {
          stockCode = stockCode + ".T";
        }

        const pendingShares =
          Number(sharesOption?.value);

        if (
          !stockCode ||
          !Number.isInteger(pendingShares) ||
          pendingShares <= 0
        ) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ 銘柄コードと注文株数を確認してください。",
              flags: 64
            }
          });
        }

        await env.DB.prepare(
          `
          INSERT INTO sbi_pending_orders (
            code,
            shares,
            created_at,
            updated_at
          )
          VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
          ON CONFLICT(code)
          DO UPDATE SET
            shares = excluded.shares,
            updated_at = CURRENT_TIMESTAMP
          `
        )
          .bind(stockCode, pendingShares)
          .run();

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: `🕒 SBI注文中に登録 | ${stockCode}`,
              description:
                "まだ保有株や損益には反映していません。",
              color: 0xD6A11D,
              fields: [
                {
                  name: "📋 注文株数",
                  value: `${pendingShares}株`,
                  inline: true
                },
                {
                  name: "➡️ 約定後",
                  value:
                    `\`/sbi 約定 code:${stockCode.replace(".T", "")} price:実際の約定単価\``,
                  inline: false
                }
              ],
              footer: {
                text:
                  "注文が取り消された場合は /sbi 取消 を実行してください"
              }
            }]
          }
        });
      }

      // /sbi 約定
      if (subcommand === "約定") {
        const codeOption =
          subcommandOptions.find(
            option => option.name === "code"
          );
        const priceOption =
          subcommandOptions.find(
            option => option.name === "price"
          );

        let stockCode =
          String(codeOption?.value || "")
            .trim()
            .toUpperCase();

        if (
          stockCode.length === 4 &&
          /^\d{4}$/.test(stockCode)
        ) {
          stockCode = stockCode + ".T";
        }

        const buyPrice =
          Number(priceOption?.value);

        if (
          !stockCode ||
          !Number.isFinite(buyPrice) ||
          buyPrice <= 0
        ) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ 銘柄コードと実際の約定価格を確認してください。",
              flags: 64
            }
          });
        }

        const pending = await env.DB.prepare(
          `
          SELECT shares
          FROM sbi_pending_orders
          WHERE code = ?
          `
        )
          .bind(stockCode)
          .first();

        if (!pending) {
          return Response.json({
            type: 4,
            data: {
              content:
                `❌ **${stockCode}** は注文中に登録されていません。\n` +
                "先に `/sbi 注文中` で登録するか、従来の `/sbi 購入` を使ってください。",
              flags: 64
            }
          });
        }

        const buyShares =
          Number(pending.shares);

        const current = await env.DB.prepare(
          `
          SELECT shares, avg_price
          FROM sbi_portfolio
          WHERE code = ?
          `
        )
          .bind(stockCode)
          .first();

        const oldShares =
          Number(current?.shares || 0);
        const oldAvgPrice =
          Number(current?.avg_price || 0);
        const totalShares =
          oldShares + buyShares;
        const newAvgPrice =
          (
            oldShares * oldAvgPrice +
            buyShares * buyPrice
          ) / totalShares;

        await env.DB.batch([
          env.DB.prepare(
            `
            INSERT INTO sbi_portfolio (
              code,
              shares,
              avg_price,
              updated_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(code)
            DO UPDATE SET
              shares = excluded.shares,
              avg_price = excluded.avg_price,
              updated_at = CURRENT_TIMESTAMP
            `
          ).bind(
            stockCode,
            totalShares,
            newAvgPrice
          ),
          env.DB.prepare(
            `
            INSERT INTO sbi_transactions (
              code,
              type,
              shares,
              price
            )
            VALUES (?, 'buy', ?, ?)
            `
          ).bind(
            stockCode,
            buyShares,
            buyPrice
          ),
          env.DB.prepare(
            "DELETE FROM sbi_pending_orders WHERE code = ?"
          ).bind(stockCode)
        ]);

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: `✅ SBI約定を記録 | ${stockCode}`,
              description:
                "注文中から保有株へ移しました。",
              color: 0x2E8B57,
              fields: [
                {
                  name: "🛒 今回の約定",
                  value:
                    `${buyShares}株 × ` +
                    `${buyPrice.toLocaleString("ja-JP")}円`,
                  inline: false
                },
                {
                  name: "📦 合計保有数",
                  value: `${totalShares}株`,
                  inline: true
                },
                {
                  name: "💰 平均取得単価",
                  value:
                    `${newAvgPrice.toLocaleString("ja-JP", {
                      maximumFractionDigits: 2
                    })}円`,
                  inline: true
                }
              ]
            }]
          }
        });
      }

      // /sbi 取消
      if (subcommand === "取消") {
        const codeOption =
          subcommandOptions.find(
            option => option.name === "code"
          );

        let stockCode =
          String(codeOption?.value || "")
            .trim()
            .toUpperCase();

        if (
          stockCode.length === 4 &&
          /^\d{4}$/.test(stockCode)
        ) {
          stockCode = stockCode + ".T";
        }

        if (!stockCode) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ 銘柄コードを確認してください。",
              flags: 64
            }
          });
        }

        const pending = await env.DB.prepare(
          `
          SELECT shares
          FROM sbi_pending_orders
          WHERE code = ?
          `
        )
          .bind(stockCode)
          .first();

        if (!pending) {
          return Response.json({
            type: 4,
            data: {
              content:
                `❌ **${stockCode}** は注文中に登録されていません。`,
              flags: 64
            }
          });
        }

        await env.DB.prepare(
          "DELETE FROM sbi_pending_orders WHERE code = ?"
        )
          .bind(stockCode)
          .run();

        return Response.json({
          type: 4,
          data: {
            embeds: [{
              title: `🗑️ SBI注文中から取消 | ${stockCode}`,
              description:
                `${Number(pending.shares)}株の仮記録を削除しました。\n` +
                "保有株と売買履歴には変更ありません。",
              color: 0x6B7280
            }]
          }
        });
      }

      // /sbi 購入
      if (subcommand === "購入") {
        const codeOption =
          subcommandOptions.find(
            option => option.name === "code"
          );
        const sharesOption =
          subcommandOptions.find(
            option => option.name === "shares"
          );
        const priceOption =
          subcommandOptions.find(
            option => option.name === "price"
          );

        let stockCode =
          String(codeOption?.value || "")
            .trim()
            .toUpperCase();

        if (
          stockCode.length === 4 &&
          /^\d{4}$/.test(stockCode)
        ) {
          stockCode = stockCode + ".T";
        }

        const buyShares =
          Number(sharesOption?.value);
        const buyPrice =
          Number(priceOption?.value);

        if (
          !stockCode ||
          !Number.isInteger(buyShares) ||
          buyShares <= 0 ||
          !Number.isFinite(buyPrice) ||
          buyPrice <= 0
        ) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ 銘柄コード・株数・約定価格を確認してください。",
              flags: 64
            }
          });
        }

        const current = await env.DB.prepare(
          `
          SELECT shares, avg_price
          FROM sbi_portfolio
          WHERE code = ?
          `
        )
          .bind(stockCode)
          .first();

        const oldShares =
          Number(current?.shares || 0);
        const oldAvgPrice =
          Number(current?.avg_price || 0);
        const totalShares =
          oldShares + buyShares;
        const newAvgPrice =
          (
            oldShares * oldAvgPrice +
            buyShares * buyPrice
          ) / totalShares;

        await env.DB.batch([
          env.DB.prepare(
            `
            INSERT INTO sbi_portfolio (
              code,
              shares,
              avg_price,
              updated_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(code)
            DO UPDATE SET
              shares = excluded.shares,
              avg_price = excluded.avg_price,
              updated_at = CURRENT_TIMESTAMP
            `
          ).bind(
            stockCode,
            totalShares,
            newAvgPrice
          ),
          env.DB.prepare(
            `
            INSERT INTO sbi_transactions (
              code,
              type,
              shares,
              price
            )
            VALUES (?, 'buy', ?, ?)
            `
          ).bind(
            stockCode,
            buyShares,
            buyPrice
          )
        ]);

        return Response.json({
          type: 4,
          data: {
            embeds: [
              {
                title: `✅ SBI購入を記録 | ${stockCode}`,
                color: 0x2E8B57,
                fields: [
                  {
                    name: "🛒 今回の購入",
                    value:
                      `${buyShares}株 × ` +
                      `${buyPrice.toLocaleString("ja-JP")}円`,
                    inline: false
                  },
                  {
                    name: "📦 合計保有数",
                    value: `${totalShares}株`,
                    inline: true
                  },
                  {
                    name: "💰 平均取得単価",
                    value:
                      `${newAvgPrice.toLocaleString("ja-JP", {
                        maximumFractionDigits: 2
                      })}円`,
                    inline: true
                  }
                ],
                footer: {
                  text:
                    "SBI証券で実際に約定した内容だけを記録してください"
                }
              }
            ]
          }
        });
      }

      // /sbi 保有
      if (subcommand === "保有") {
        const result = await env.DB.prepare(
          `
          SELECT code, shares, avg_price
          FROM sbi_portfolio
          ORDER BY code
          `
        ).run();

        const rows = result.results || [];

        if (rows.length === 0) {
          return Response.json({
            type: 4,
            data: {
              embeds: [
                {
                  title: "📦 SBI保有株",
                  description:
                    "まだ保有株は記録されていません。\n" +
                    "約定後に `/sbi 購入` で記録できます。",
                  color: 0x6B7280
                }
              ]
            }
          });
        }

        const fields = rows.slice(0, 25).map(row => {
          const shares = Number(row.shares);
          const avgPrice = Number(row.avg_price);
          const cost = shares * avgPrice;

          return {
            name: `🏷️ ${row.code}`,
            value:
              `保有：${shares}株\n` +
              `平均取得単価：${avgPrice.toLocaleString("ja-JP", {
                maximumFractionDigits: 2
              })}円\n` +
              `取得額：約${cost.toLocaleString("ja-JP", {
                maximumFractionDigits: 0
              })}円`,
            inline: true
          };
        });

        return Response.json({
          type: 4,
          data: {
            embeds: [
              {
                title: "📦 SBI保有株一覧",
                description:
                  `${rows.length}銘柄を記録中`,
                color: 0x1D5FA7,
                fields: fields,
                footer: {
                  text:
                    "この一覧はDiscordで記録した内容です"
                }
              }
            ]
          }
        });
      }

      // /sbi 売却
      if (subcommand === "売却") {
        const codeOption =
          subcommandOptions.find(
            option => option.name === "code"
          );
        const sharesOption =
          subcommandOptions.find(
            option => option.name === "shares"
          );
        const priceOption =
          subcommandOptions.find(
            option => option.name === "price"
          );

        let stockCode =
          String(codeOption?.value || "")
            .trim()
            .toUpperCase();

        if (
          stockCode.length === 4 &&
          /^\d{4}$/.test(stockCode)
        ) {
          stockCode = stockCode + ".T";
        }

        const sellShares =
          Number(sharesOption?.value);
        const sellPrice =
          Number(priceOption?.value);

        if (
          !stockCode ||
          !Number.isInteger(sellShares) ||
          sellShares <= 0 ||
          !Number.isFinite(sellPrice) ||
          sellPrice <= 0
        ) {
          return Response.json({
            type: 4,
            data: {
              content:
                "❌ 銘柄コード・株数・約定価格を確認してください。",
              flags: 64
            }
          });
        }

        const current = await env.DB.prepare(
          `
          SELECT shares, avg_price
          FROM sbi_portfolio
          WHERE code = ?
          `
        )
          .bind(stockCode)
          .first();

        if (!current) {
          return Response.json({
            type: 4,
            data: {
              content:
                `❌ **${stockCode}** はSBI保有株に記録されていません。`,
              flags: 64
            }
          });
        }

        const oldShares = Number(current.shares);
        const avgPrice = Number(current.avg_price);

        if (sellShares > oldShares) {
          return Response.json({
            type: 4,
            data: {
              content:
                `❌ 売却株数が保有数を超えています。\n` +
                `現在の保有：${oldShares}株`,
              flags: 64
            }
          });
        }

        const remainingShares =
          oldShares - sellShares;
        const realizedProfit =
          (sellPrice - avgPrice) * sellShares;
        const estimatedTax =
          Math.max(realizedProfit, 0) * 0.20315;
        const netProfit =
          realizedProfit - estimatedTax;

        const portfolioStatement =
          remainingShares === 0
            ? env.DB.prepare(
                "DELETE FROM sbi_portfolio WHERE code = ?"
              ).bind(stockCode)
            : env.DB.prepare(
                `
                UPDATE sbi_portfolio
                SET shares = ?, updated_at = CURRENT_TIMESTAMP
                WHERE code = ?
                `
              ).bind(remainingShares, stockCode);

        await env.DB.batch([
          portfolioStatement,
          env.DB.prepare(
            `
            INSERT INTO sbi_transactions (
              code,
              type,
              shares,
              price,
              realized_profit,
              estimated_tax,
              net_profit
            )
            VALUES (?, 'sell', ?, ?, ?, ?, ?)
            `
          ).bind(
            stockCode,
            sellShares,
            sellPrice,
            realizedProfit,
            estimatedTax,
            netProfit
          )
        ]);

        const resultColor =
          realizedProfit >= 0
            ? 0x2E8B57
            : 0xC0392B;

        return Response.json({
          type: 4,
          data: {
            embeds: [
              {
                title: `💵 SBI売却を記録 | ${stockCode}`,
                color: resultColor,
                fields: [
                  {
                    name: "💹 今回の売却",
                    value:
                      `${sellShares}株 × ` +
                      `${sellPrice.toLocaleString("ja-JP")}円`,
                    inline: false
                  },
                  {
                    name: "📊 税引前実現損益",
                    value:
                      `${realizedProfit >= 0 ? "+" : ""}` +
                      `${realizedProfit.toLocaleString("ja-JP", {
                        maximumFractionDigits: 0
                      })}円`,
                    inline: true
                  },
                  {
                    name: "🧾 概算税額",
                    value:
                      `${estimatedTax.toLocaleString("ja-JP", {
                        maximumFractionDigits: 0
                      })}円`,
                    inline: true
                  },
                  {
                    name: "💰 概算税引後損益",
                    value:
                      `**${netProfit >= 0 ? "+" : ""}` +
                      `${netProfit.toLocaleString("ja-JP", {
                        maximumFractionDigits: 0
                      })}円**`,
                    inline: false
                  },
                  {
                    name: "📦 残り保有数",
                    value: `${remainingShares}株`,
                    inline: false
                  }
                ],
                footer: {
                  text:
                    "税額は20.315%の単純計算です。実際は特定口座内の年間損益で調整されます"
                }
              }
            ]
          }
        });
      }

      // /sbi 履歴
      if (subcommand === "履歴") {
        const result = await env.DB.prepare(
          `
          SELECT
            code,
            type,
            shares,
            price,
            realized_profit,
            estimated_tax,
            net_profit,
            datetime(created_at, '+9 hours') AS created_at_jst
          FROM sbi_transactions
          ORDER BY id DESC
          LIMIT 20
          `
        ).run();

        const rows = result.results || [];

        if (rows.length === 0) {
          return Response.json({
            type: 4,
            data: {
              embeds: [
                {
                  title: "📘 SBI売買履歴",
                  description:
                    "まだ購入・売却は記録されていません。",
                  color: 0x6B7280
                }
              ]
            }
          });
        }

        const fields = rows.map(row => {
          const shares = Number(row.shares);
          const price = Number(row.price);

          if (row.type === "buy") {
            return {
              name: `🛒 購入 | ${row.code}`,
              value:
                `${shares}株 × ${price.toLocaleString("ja-JP")}円\n` +
                `日時：${row.created_at_jst}`,
              inline: false
            };
          }

          const realizedProfit =
            Number(row.realized_profit);
          const netProfit =
            Number(row.net_profit);

          return {
            name: `💵 売却 | ${row.code}`,
            value:
              `${shares}株 × ${price.toLocaleString("ja-JP")}円\n` +
              `税引前：${realizedProfit >= 0 ? "+" : ""}` +
              `${realizedProfit.toLocaleString("ja-JP", {
                maximumFractionDigits: 0
              })}円\n` +
              `概算税引後：${netProfit >= 0 ? "+" : ""}` +
              `${netProfit.toLocaleString("ja-JP", {
                maximumFractionDigits: 0
              })}円\n` +
              `日時：${row.created_at_jst}`,
            inline: false
          };
        });

        return Response.json({
          type: 4,
          data: {
            embeds: [
              {
                title: "📘 SBI売買履歴（最新20件）",
                color: 0x1D5FA7,
                fields: fields,
                footer: {
                  text:
                    "SBI証券で約定後にDiscordへ記録した履歴です"
                }
              }
            ]
          }
        });
      }

      // /sbi 損益
      if (subcommand === "損益") {
        const result = await env.DB.prepare(
          `
          SELECT
            COUNT(*) AS sell_count,
            COALESCE(
              SUM(CASE WHEN realized_profit > 0 THEN realized_profit ELSE 0 END),
              0
            ) AS total_gain,
            COALESCE(
              SUM(CASE WHEN realized_profit < 0 THEN realized_profit ELSE 0 END),
              0
            ) AS total_loss,
            COALESCE(SUM(realized_profit), 0) AS total_profit
          FROM sbi_transactions
          WHERE type = 'sell'
          `
        ).first();

        const sellCount =
          Number(result?.sell_count || 0);

        if (sellCount === 0) {
          return Response.json({
            type: 4,
            data: {
              embeds: [
                {
                  title: "📊 SBI実現損益",
                  description:
                    "まだ売却は記録されていません。",
                  color: 0x6B7280
                }
              ]
            }
          });
        }

        const totalGain =
          Number(result.total_gain || 0);
        const totalLoss =
          Number(result.total_loss || 0);
        const totalProfit =
          Number(result.total_profit || 0);
        const estimatedTax =
          Math.max(totalProfit, 0) * 0.20315;
        const netProfit =
          totalProfit - estimatedTax;
        const color =
          totalProfit >= 0
            ? 0x2E8B57
            : 0xC0392B;

        return Response.json({
          type: 4,
          data: {
            embeds: [
              {
                title: "📊 SBI実現損益",
                description:
                  `売却回数：${sellCount}回`,
                color: color,
                fields: [
                  {
                    name: "📈 利益合計",
                    value:
                      `+${totalGain.toLocaleString("ja-JP", {
                        maximumFractionDigits: 0
                      })}円`,
                    inline: true
                  },
                  {
                    name: "📉 損失合計",
                    value:
                      `${totalLoss.toLocaleString("ja-JP", {
                        maximumFractionDigits: 0
                      })}円`,
                    inline: true
                  },
                  {
                    name: "💹 税引前実現損益",
                    value:
                      `**${totalProfit >= 0 ? "+" : ""}` +
                      `${totalProfit.toLocaleString("ja-JP", {
                        maximumFractionDigits: 0
                      })}円**`,
                    inline: false
                  },
                  {
                    name: "🧾 概算税額",
                    value:
                      `${estimatedTax.toLocaleString("ja-JP", {
                        maximumFractionDigits: 0
                      })}円`,
                    inline: true
                  },
                  {
                    name: "💰 概算税引後損益",
                    value:
                      `**${netProfit >= 0 ? "+" : ""}` +
                      `${netProfit.toLocaleString("ja-JP", {
                        maximumFractionDigits: 0
                      })}円**`,
                    inline: false
                  }
                ],
                footer: {
                  text:
                    "利益と損失を合算後、20.315%で単純計算した概算です"
                }
              }
            ]
          }
        });
      }

      if (
        subcommand !== "状態" &&
        subcommand !== "設定"
      ) {
        return Response.json({
          type: 4,
          data: {
            content:
              "❌ Discordの `/sbi` メニューから操作を選んでください。",
            flags: 64
          }
        });
      }

      const capitalText =
        capital > 0
          ? `${capital.toLocaleString("ja-JP")}円`
          : "未設定";

      const statusText =
        capital > 0
          ? "✅ 準備OK"
          : "⚠️ 運用資金を設定してください";

      const nextStep =
        capital > 0
          ? "`/sbi 分析` で銘柄を分析できます。"
          : "`/sbi 設定 capital:70000` のように運用資金を設定してください。";

      const description =
        subcommand === "設定"
          ? "✅ 運用資金を更新しました。"
          : "少額の短期売買を、判断しやすい形でサポートします。";

      return Response.json({
        type: 4,
        data: {
          embeds: [
            {
              title: "SBI短期売買支援AI",
              description: description,
              color: 0x1D5FA7,
              fields: [
                {
                  name: "💰 運用資金",
                  value: capitalText,
                  inline: true
                },
                {
                  name: "🏦 口座",
                  value: "特定口座（源泉徴収あり）",
                  inline: true
                },
                {
                  name: "📌 現在の状態",
                  value: statusText,
                  inline: false
                },
                {
                  name: "➡️ 次の操作",
                  value: nextStep,
                  inline: false
                }
              ],
              footer: {
                text:
                  "売買の最終判断と注文はSBI証券で行ってください"
              }
            }
          ]
        }
      });
    }

    // /sbi分析
    if (command === "sbi分析") {
      const codeOption =
        interaction.data?.options?.find(
          option => option.name === "code"
        );

      let stockCode =
        String(codeOption?.value || "")
          .trim()
          .toUpperCase();

      if (
        stockCode.length === 4 &&
        /^\d{4}$/.test(stockCode)
      ) {
        stockCode = stockCode + ".T";
      }

      if (!stockCode) {
        return Response.json({
          type: 4,
          data: {
            content:
              "❌ 銘柄コードを入力してください。",
            flags: 64
          }
        });
      }

      const channelId = interaction.channel_id;

      if (!channelId) {
        return Response.json({
          type: 4,
          data: {
            content:
              "❌ Discordチャンネルを取得できませんでした。",
            flags: 64
          }
        });
      }

      await env.DB.prepare(
        `
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        `
      ).run();

      const saved = await env.DB.prepare(
        `
        SELECT value
        FROM app_settings
        WHERE key = 'sbi_capital'
        `
      ).first();

      const capital = Number(saved?.value || 0);

      if (!Number.isFinite(capital) || capital <= 0) {
        return Response.json({
          type: 4,
          data: {
            content:
              "⚠️ 先に `/sbi capital:70000` のように運用資金を設定してください。",
            flags: 64
          }
        });
      }

      ctx.waitUntil(
        startGitHubAction(
          env,
          stockCode,
          channelId,
          "sbi_analysis",
          "[]",
          "0",
          String(capital)
        ).catch(error => {
          console.error(error);
        })
      );

      return Response.json({
        type: 4,
        data: {
          embeds: [
            {
              title: "⏳ SBI短期売買プランを計算中",
              description:
                `**${stockCode}** の株価と値動きを確認しています。\n` +
                "完了後、このチャンネルにプランを送信します。",
              color: 0xD6A11D
            }
          ]
        }
      });
    }

    // /保有追加
if (command === "保有追加") {
  const codeOption =
    interaction.data?.options?.find(
      option => option.name === "code"
    );

  const sharesOption =
    interaction.data?.options?.find(
      option => option.name === "shares"
    );

  const avgPriceOption =
    interaction.data?.options?.find(
      option => option.name === "avg_price"
    );

  let code =
    String(codeOption?.value || "")
      .trim()
      .toUpperCase();

  if (code.length === 4 && /^\d{4}$/.test(code)) {
    code = code + ".T";
  }

  const shares =
    Number(sharesOption?.value);

  const avgPrice =
    Number(avgPriceOption?.value);

  if (
    !code ||
    !Number.isFinite(shares) ||
    shares <= 0 ||
    !Number.isFinite(avgPrice) ||
    avgPrice <= 0
  ) {
    return Response.json({
      type: 4,
      data: {
        content:
          "❌ 銘柄コード・株数・平均取得単価を確認してください。"
      }
    });
  }

  await env.DB.prepare(
    `
    INSERT INTO portfolio (
      code,
      shares,
      avg_price,
      updated_at
    )
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(code)
    DO UPDATE SET
      shares = excluded.shares,
      avg_price = excluded.avg_price,
      updated_at = CURRENT_TIMESTAMP
    `
  )
    .bind(
      code,
      shares,
      avgPrice
    )
    .run();

  return Response.json({
    type: 4,
    data: {
      content:
        `✅ **${code}** を保有株に保存しました。\n` +
        `株数：${shares}\n` +
        `平均取得単価：${avgPrice}`
    }
  });
}
// /保有一覧
if (command === "保有一覧") {
  const result = await env.DB.prepare(
    `
    SELECT
      code,
      shares,
      avg_price
    FROM portfolio
    ORDER BY code
    `
  ).run();

  const rows = result.results || [];

  if (rows.length === 0) {
    return Response.json({
      type: 4,
      data: {
        content:
          "📭 まだ保有株は登録されていません。"
      }
    });
  }

  const lines = rows.map(
    row =>
      `🏷️ **${row.code}**\n` +
      `株数：${row.shares}\n` +
      `平均取得単価：${row.avg_price}`
  );

  return Response.json({
    type: 4,
    data: {
      content:
        "📦 **保有株一覧**\n\n" +
        lines.join("\n\n")
    }
  });
}
// /保有削除
if (command === "保有削除") {
  const codeOption =
    interaction.data?.options?.find(
      option => option.name === "code"
    );

  let code =
    String(codeOption?.value || "")
      .trim()
      .toUpperCase();

  // 6501 → 6501.T
  if (code.length === 4 && /^\d{4}$/.test(code)) {
    code = code + ".T";
  }

  if (!code) {
    return Response.json({
      type: 4,
      data: {
        content:
          "❌ 削除する銘柄コードを入力してください。"
      }
    });
  }

  const existing = await env.DB.prepare(
    "SELECT code FROM portfolio WHERE code = ?"
  )
    .bind(code)
    .first();

  if (!existing) {
    return Response.json({
      type: 4,
      data: {
        content:
          `❌ **${code}** は保有株に登録されていません。`
      }
    });
  }

  await env.DB.prepare(
    "DELETE FROM portfolio WHERE code = ?"
  )
    .bind(code)
    .run();

  return Response.json({
    type: 4,
    data: {
      content:
        `🗑️ **${code}** を保有株から削除しました。`
    }
  });
}
// /買い増し
if (command === "買い増し") {
  const codeOption =
    interaction.data?.options?.find(
      option => option.name === "code"
    );

  const sharesOption =
    interaction.data?.options?.find(
      option => option.name === "shares"
    );

  const priceOption =
    interaction.data?.options?.find(
      option => option.name === "price"
    );

  let code =
    String(codeOption?.value || "")
      .trim()
      .toUpperCase();

  // 6501 → 6501.T
  if (code.length === 4 && /^\d{4}$/.test(code)) {
    code = code + ".T";
  }

  const addShares =
    Number(sharesOption?.value);

  const buyPrice =
    Number(priceOption?.value);

  if (
    !code ||
    !Number.isFinite(addShares) ||
    addShares <= 0 ||
    !Number.isFinite(buyPrice) ||
    buyPrice <= 0
  ) {
    return Response.json({
      type: 4,
      data: {
        content:
          "❌ 銘柄コード・買い増し株数・購入価格を確認してください。"
      }
    });
  }

  const current = await env.DB.prepare(
    `
    SELECT
      code,
      shares,
      avg_price
    FROM portfolio
    WHERE code = ?
    `
  )
    .bind(code)
    .first();

  if (!current) {
    return Response.json({
      type: 4,
      data: {
        content:
          `❌ **${code}** はまだ保有株に登録されていません。\n` +
          "先に `/保有追加` で登録してください。"
      }
    });
  }

  const oldShares =
    Number(current.shares);

  const oldAvgPrice =
    Number(current.avg_price);

  const newShares =
    oldShares + addShares;

  const newAvgPrice =
    (
      oldShares * oldAvgPrice +
      addShares * buyPrice
    ) / newShares;

  await env.DB.prepare(
    `
    UPDATE portfolio
    SET
      shares = ?,
      avg_price = ?,
      updated_at = CURRENT_TIMESTAMP
    WHERE code = ?
    `
  )
    .bind(
      newShares,
      newAvgPrice,
      code
    )
    .run();
    await env.DB.prepare(
  `
  INSERT INTO transactions (
    code,
    type,
    shares,
    price,
    realized_profit
  )
  VALUES (?, ?, ?, ?, ?)
  `
)
  .bind(
    code,
    "buy",
    addShares,
    buyPrice,
    0
  )
  .run();
  return Response.json({
    type: 4,
    data: {
      content:
        `🛒 **${code} を買い増しました**\n\n` +
        `追加株数：${addShares}\n` +
        `購入価格：${buyPrice.toLocaleString()}円\n\n` +
        `📦 合計株数：${newShares}\n` +
        `💰 新しい平均取得単価：${newAvgPrice.toFixed(2)}円`
    }
  });
}

// /売買履歴
if (command === "売買履歴") {
  const result = await env.DB.prepare(
    `
    SELECT
      code,
      type,
      shares,
      price,
      realized_profit,
      datetime(created_at, '+9 hours') AS created_at_jst
    FROM transactions
    ORDER BY id DESC
    LIMIT 20
    `
  ).run();

  const rows = result.results || [];

  if (rows.length === 0) {
    return Response.json({
      type: 4,
      data: {
        content:
          "📭 まだ売買履歴はありません。"
      }
    });
  }

  const lines = rows.map(row => {
    const typeText =
      row.type === "buy"
        ? "🛒 買い増し"
        : "💵 売却";

    let text =
      `${typeText} **${row.code}**\n` +
      `株数：${row.shares}\n` +
      `価格：${Number(row.price).toLocaleString()}円\n` +
      `日時：${row.created_at_jst}`;

    if (row.type === "sell") {
      const profit =
        Number(row.realized_profit);

      const mark =
        profit >= 0 ? "🟢" : "🔴";

      text +=
        `\n${mark} 実現損益：` +
        `${profit >= 0 ? "+" : ""}` +
        `${profit.toLocaleString()}円`;
    }

    return text;
  });

  return Response.json({
    type: 4,
    data: {
      content:
        "📚 **売買履歴（最新20件）**\n\n" +
        lines.join("\n\n")
    }
  });
}

// /実現損益
if (command === "実現損益") {
  const result = await env.DB.prepare(
    `
    SELECT
      COUNT(*) AS sell_count,
      COALESCE(
        SUM(
          CASE
            WHEN realized_profit > 0
            THEN realized_profit
            ELSE 0
          END
        ),
        0
      ) AS total_gain,
      COALESCE(
        SUM(
          CASE
            WHEN realized_profit < 0
            THEN realized_profit
            ELSE 0
          END
        ),
        0
      ) AS total_loss,
      COALESCE(
        SUM(realized_profit),
        0
      ) AS total_profit
    FROM transactions
    WHERE type = 'sell'
    `
  ).first();

  const sellCount =
    Number(result?.sell_count || 0);

  const totalGain =
    Number(result?.total_gain || 0);

  const totalLoss =
    Number(result?.total_loss || 0);

  const totalProfit =
    Number(result?.total_profit || 0);

  if (sellCount === 0) {
    return Response.json({
      type: 4,
      data: {
        content:
          "📭 まだ売却履歴がありません。"
      }
    });
  }

  const mark =
    totalProfit >= 0 ? "🟢" : "🔴";

  return Response.json({
    type: 4,
    data: {
      content:
        "💰 **実現損益**\n\n" +
        `売却回数：${sellCount}回\n` +
        `📈 利益合計：+${totalGain.toLocaleString()}円\n` +
        `📉 損失合計：${totalLoss.toLocaleString()}円\n\n` +
        `${mark} **合計実現損益：` +
        `${totalProfit >= 0 ? "+" : ""}` +
        `${totalProfit.toLocaleString()}円**`
    }
  });
}

// /保有分析
if (command === "保有分析") {
  const result = await env.DB.prepare(
    `
    SELECT
      code,
      shares,
      avg_price
    FROM portfolio
    ORDER BY code
    `
  ).run();

  const portfolio = result.results || [];

  if (portfolio.length === 0) {
    return Response.json({
      type: 4,
      data: {
        content:
          "📭 保有株が登録されていません。"
      }
    });
  }
// /一部売却
if (command === "一部売却") {
  const codeOption =
    interaction.data?.options?.find(
      option => option.name === "code"
    );

  const sharesOption =
    interaction.data?.options?.find(
      option => option.name === "shares"
    );

  const priceOption =
    interaction.data?.options?.find(
      option => option.name === "price"
    );

  let code =
    String(codeOption?.value || "")
      .trim()
      .toUpperCase();

  // 6501 → 6501.T
  if (code.length === 4 && /^\d{4}$/.test(code)) {
    code = code + ".T";
  }

  const sellShares =
    Number(sharesOption?.value);

  const sellPrice =
    Number(priceOption?.value);

  if (
    !code ||
    !Number.isFinite(sellShares) ||
    sellShares <= 0 ||
    !Number.isFinite(sellPrice) ||
    sellPrice <= 0
  ) {
    return Response.json({
      type: 4,
      data: {
        content:
          "❌ 銘柄コード・売却株数・売却価格を確認してください。"
      }
    });
  }

  const current = await env.DB.prepare(
    `
    SELECT
      code,
      shares,
      avg_price
    FROM portfolio
    WHERE code = ?
    `
  )
    .bind(code)
    .first();

  if (!current) {
    return Response.json({
      type: 4,
      data: {
        content:
          `❌ **${code}** は保有株に登録されていません。`
      }
    });
  }

  const oldShares =
    Number(current.shares);

  const avgPrice =
    Number(current.avg_price);

  if (sellShares > oldShares) {
    return Response.json({
      type: 4,
      data: {
        content:
          `❌ 売却株数が保有株数を超えています。\n` +
          `現在の保有株数：${oldShares}`
      }
    });
  }

  const remainingShares =
    oldShares - sellShares;

  const realizedProfit =
    (sellPrice - avgPrice) * sellShares;

  // 全部売却した場合
  if (remainingShares === 0) {
    await env.DB.prepare(
      "DELETE FROM portfolio WHERE code = ?"
    )
      .bind(code)
      .run();
  } else {
    // 一部売却なら株数だけ減らす
    await env.DB.prepare(
      `
      UPDATE portfolio
      SET
        shares = ?,
        updated_at = CURRENT_TIMESTAMP
      WHERE code = ?
      `
    )
      .bind(
        remainingShares,
        code
      )
      .run();
  }
  await env.DB.prepare(
  `
  INSERT INTO transactions (
    code,
    type,
    shares,
    price,
    realized_profit
  )
  VALUES (?, ?, ?, ?, ?)
  `
)
  .bind(
    code,
    "sell",
    sellShares,
    sellPrice,
    realizedProfit
  )
  .run();
  const mark =
    realizedProfit >= 0 ? "🟢" : "🔴";

  return Response.json({
    type: 4,
    data: {
      content:
        `💵 **${code} を売却しました**\n\n` +
        `売却株数：${sellShares}\n` +
        `売却価格：${sellPrice.toLocaleString()}円\n` +
        `${mark} 実現損益：${realizedProfit >= 0 ? "+" : ""}${realizedProfit.toFixed(0)}円\n\n` +
        `📦 残り株数：${remainingShares}`
    }
  });
}
  const channelId =
    interaction.channel_id;

  if (!channelId) {
    return Response.json({
      type: 4,
      data: {
        content:
          "❌ Discordチャンネルを取得できませんでした。"
      }
    });
  }

  const portfolioJson =
    JSON.stringify(portfolio);

  ctx.waitUntil(
    startGitHubAction(
      env,
      "",
      channelId,
      "portfolio",
      portfolioJson
    ).catch(error => {
      console.error(error);
    })
  );

  return Response.json({
    type: 4,
    data: {
      content:
        "⏳ **保有株の現在価格と損益を計算しています。**\n" +
        "終わったら結果をこのチャンネルに送ります。"
    }
  });
}

// /損益まとめ
if (command === "損益まとめ") {
  // 現在の保有株を取得
  const portfolioResult = await env.DB.prepare(
    `
    SELECT
      code,
      shares,
      avg_price
    FROM portfolio
    ORDER BY code
    `
  ).run();

  const portfolio =
    portfolioResult.results || [];

  // 売却済みの実現損益を合計
  const profitResult = await env.DB.prepare(
    `
    SELECT
      COALESCE(SUM(realized_profit), 0)
      AS total_profit
    FROM transactions
    WHERE type = 'sell'
    `
  ).first();

  const realizedProfit =
    Number(profitResult?.total_profit || 0);

  const channelId =
    interaction.channel_id;

  if (!channelId) {
    return Response.json({
      type: 4,
      data: {
        content:
          "❌ Discordチャンネルを取得できませんでした。"
      }
    });
  }

  const portfolioJson =
    JSON.stringify(portfolio);

  ctx.waitUntil(
    startGitHubAction(
      env,
      "",
      channelId,
      "profit_summary",
      portfolioJson,
      String(realizedProfit)
    ).catch(error => {
      console.error(error);
    })
  );

  return Response.json({
    type: 4,
    data: {
      content:
        "⏳ **損益を集計しています。**\n" +
        "含み損益と実現損益を計算して送ります。"
    }
  });
}

    // 有料AI分析は無料運用のため停止
    if (command === "ai分析") {
      return Response.json({
        type: 4,
        data: {
          content:
            "🔒 `/ai分析` は無料運用を守るため停止中です。`/sbi 候補`・`/sbi 分析`・`/sbi 注文判断` を利用してください。",
          flags: 64
        }
      });
    }

    // /分析
    if (command === "分析") {
      const codeOption =
        interaction.data?.options?.find(
          option =>
            option.name === "code"
        );

      const stockCode =
        String(
          codeOption?.value || ""
        )
          .trim()
          .toUpperCase();

      const channelId =
        interaction.channel_id;

      if (!stockCode) {
        return Response.json({
          type: 4,
          data: {
            content:
              "❌ 銘柄コードがありません。"
          }
        });
      }

      if (!channelId) {
        return Response.json({
          type: 4,
          data: {
            content:
              "❌ Discordチャンネルを取得できませんでした。"
          }
        });
      }

      const mode = "analysis";

      // GitHub Actionsを裏で起動
      ctx.waitUntil(
        startGitHubAction(
          env,
          stockCode,
          channelId,
          mode
        ).catch(error => {
          console.error(error);
        })
      );

      return Response.json({
        type: 4,

        data: {
          content:
            `⏳ **${stockCode}** の分析を開始しました。\n` +
            "終わったら結果をこのチャンネルに送ります。"
        }
      });
    }

    return Response.json({
      type: 4,
      data: {
        content:
          "❓ 対応していないコマンドです。"
      }
    });
  },

  async scheduled(controller, env, ctx) {
    const allowedCrons = new Set([
      "0 1 * * 1-5",
      "30 4 * * 1-5"
    ]);
    if (!allowedCrons.has(controller.cron)) {
      console.log("未使用のCronをスキップ:", controller.cron);
      return;
    }

    const settingsResult = await env.DB.prepare(
      `
      SELECT key, value
      FROM app_settings
      WHERE key IN (
        'sbi_auto_enabled',
        'sbi_alert_channel_id',
        'sbi_capital'
      )
      `
    ).run();
    const settings = Object.fromEntries(
      (settingsResult.results || []).map(row => [row.key, row.value])
    );

    if (settings.sbi_auto_enabled !== "1") {
      console.log("SBI自動通知はオフです");
      return;
    }
    if (!settings.sbi_alert_channel_id) {
      console.log("SBI通知チャンネルが未設定です");
      return;
    }

    const [watchResult, portfolioResult] = await Promise.all([
      env.DB.prepare(
        `SELECT code, take_profit, stop_loss FROM sbi_watchlist ORDER BY updated_at DESC`
      ).run(),
      env.DB.prepare(
        `SELECT code, shares, avg_price FROM sbi_portfolio ORDER BY code`
      ).run()
    ]);
    const watches = watchResult.results || [];
    if (watches.length === 0) {
      console.log("監視銘柄がないためGitHub Actionsを起動しません");
      return;
    }

    ctx.waitUntil(
      startGitHubAction(
        env,
        "",
        settings.sbi_alert_channel_id,
        "sbi_auto_monitor",
        JSON.stringify(portfolioResult.results || []),
        "0",
        String(settings.sbi_capital || "0"),
        JSON.stringify(watches)
      ).catch(error => console.error(error))
    );
  }
};
