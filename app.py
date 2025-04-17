import os
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Load data ---
df = {k.strip(): v for k, v in pd.read_excel("Sharp Token.xlsx", sheet_name=None).items()}

referral_df = df["Referrals"]
wallet_df = df["Wallets Created"]
fee_df = df["POL Data"]

tokens_source_df = pd.read_excel("Sharp Token.xlsx", sheet_name="Tokens per source")
tokens_source_df["Date"] = pd.to_datetime(
    tokens_source_df["Date"], format="%m-%d-%Y", errors="coerce"
)
tokens_source_df.dropna(subset=["Date"], inplace=True)
tokens_source_df["Date"] = tokens_source_df["Date"].dt.date  # strip time
tokens_source_df["Date"] = pd.to_datetime(tokens_source_df["Date"])  # convert back to datetime

# --- Clean and prep data ---
for df_ in [wallet_df, referral_df, fee_df]:
    if "Date" in df_.columns:
        df_["Date"] = pd.to_datetime(df_["Date"], format="%Y-%m-%d", errors="coerce")
        df_.dropna(subset=["Date"], inplace=True)

referral_sources = [ col for col in referral_df.columns if col != "Date" and pd.api.types.is_numeric_dtype(referral_df[col])]
referral_df["Referrals"] = referral_df[referral_sources].sum(axis=1)

# --- Precompute Figures ---
def create_figures():
    # --- Token Charts ---
    tsdf = tokens_source_df[tokens_source_df["Date"] >= "2025-01-01"].copy()
    token_source_cols = [
        col for col in tsdf.select_dtypes(include="number").columns if col != "Total"
    ]
    monthly_tokens = tsdf.resample("MS", on="Date").sum(numeric_only=True).reset_index()
    monthly_tokens["Month"] = monthly_tokens["Date"]  # Keep this for time-based charts
    monthly_tokens["MonthLabel"] = monthly_tokens["Date"].dt.strftime("%B %Y")  # For display only

    if "Total" not in monthly_tokens.columns:
        monthly_tokens["Total"] = monthly_tokens[token_source_cols].sum(axis=1)
    total_tokens = monthly_tokens["Total"].sum()

    token_bar = px.bar(
        monthly_tokens,
        x="Month",
        y="Total",
        title=f"Monthly Token Distribution (Total: {total_tokens:,.0f})",
        text="Total",
    )
    token_bar.update_traces(texttemplate="%{text:,.0f}", textposition="auto")
    token_bar.update_layout(xaxis_tickangle=-45)

    token_line = px.line(
        monthly_tokens,
        x="Month",
        y="Total",
        title=f"Monthly Token Growth Over Time (Total: {total_tokens:,.0f})",
        markers=True
    )
    token_line.update_traces(name="Total Tokens", legendgroup="Total Tokens")
    token_line.update_layout(
        showlegend=True,
        legend=dict(title="Legend", x=0.8, y=1, traceorder="normal", orientation="v"),
    )

    # --- Wallet Charts ---
    wallet_df_filtered = wallet_df[wallet_df["Date"] > "2024-12-31"].copy()
    wallet_df_filtered["Month"] = (wallet_df_filtered["Date"].dt.to_period("M").dt.to_timestamp())
    monthly_wallets = (wallet_df_filtered.groupby("Month")[["Android", "iOS", "Web"]].sum().reset_index())
    platform_totals = monthly_wallets[["Android", "iOS", "Web"]].sum().astype(int)

    wallets_melted = monthly_wallets.melt(
        id_vars="Month",
        value_vars=["Android", "iOS", "Web"],
        var_name="Platform",
        value_name="Count",
    )

    wallet_bar = px.bar(
        wallets_melted,
        x="Month",
        y="Count",
        color="Platform",
        barmode="group",
        title=(
            f"Monthly Wallet Creation by Platform<br>"
            f"Total: {platform_totals.sum():,} | "
            f'Android: {platform_totals["Android"]:,} | '
            f'iOS: {platform_totals["iOS"]:,} | '
            f'Web: {platform_totals["Web"]:,}'
        ),
    )
    wallet_bar.update_layout(xaxis_tickangle=-45)

    wallet_pie = px.pie(
        names=platform_totals.index,
        values=platform_totals.values,
        hole=0.4,
        title=(
            f"Wallet Platform Distribution<br>"
            f"Total: {platform_totals.sum():,} | "
            f'Android: {platform_totals["Android"]:,} | '
            f'iOS: {platform_totals["iOS"]:,} | '
            f'Web: {platform_totals["Web"]:,}'
        ),
    )

    # --- Referrals ---
    rdf = referral_df[referral_df["Date"] >= "2025-01-01"].copy()
    rdf["Month"] = rdf["Date"].dt.to_period("M").dt.to_timestamp()
    referral_by_source = rdf.groupby("Month")[referral_sources].sum().reset_index()
    referral_totals = referral_by_source[referral_sources].sum().astype(int)

    referral_melted = referral_by_source.melt(
        id_vars="Month",
        value_vars=referral_sources,
        var_name="Campaign",
        value_name="Referrals",
    )
    referral_bar = px.bar(
        referral_melted,
        x="Month",
        y="Referrals",
        color="Campaign",
        title=f"Monthly Referrals by Source (Total: {referral_totals.sum():,})",
        barmode="stack",
        color_discrete_sequence=px.colors.qualitative.Vivid,  # 👈 more distinct colors
    )
    # Add total labels above each stacked bar
    referral_totals_by_month = referral_melted.groupby("Month")["Referrals"].sum().reset_index()
    
    referral_bar.add_trace(
        go.Scatter(
            x=referral_totals_by_month["Month"],
            y=referral_totals_by_month["Referrals"],
            text=referral_totals_by_month["Referrals"].apply(lambda x: f"{int(x):,}"),
            mode="text",
            textposition="top center",
            showlegend=False,
        )
    )

    referral_by_source["Total"] = referral_by_source[referral_sources].sum(axis=1)
    referral_line = px.line(
        referral_by_source,
        x="Month",
        y="Total",
        title="Monthly Total Referrals Over Time (From Jan 2025)",
        markers=True,
    )

    # --- Fee Chart ---
    fdf = fee_df[fee_df["Date"] > "2024-12-31"].copy()
    fdf["Month"] = fdf["Date"].dt.to_period("M").dt.to_timestamp()
    monthly_fee = fdf.groupby("Month")["TxnFee(POL)"].sum().reset_index()
    total_fee = int(monthly_fee["TxnFee(POL)"].sum())

    fee_line = px.line(
        monthly_fee,
        x="Month",
        y="TxnFee(POL)",
        title=f"Transaction Fee Trends by Month (Total: {total_fee:,} POL)",
        markers=True,
    )

    # --- Total Tokens by Source (Horizontal Bar) ---
    total_tokens = tokens_source_df[token_source_cols].sum().reset_index()
    total_tokens.columns = ["Source", "Total Tokens"]

    token_source_bar = px.bar(
        total_tokens,
        x="Total Tokens",
        y="Source",
        orientation="h",
        color="Source",
        title=f'Total Tokens by Source (Total: {int(total_tokens["Total Tokens"].sum()):,})',
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    token_source_bar.update_traces(
        text=total_tokens["Total Tokens"],
        texttemplate="%{x:,.0f}",
        insidetextanchor="middle",
    )
    token_source_bar.update_layout(
        showlegend=False,
        uniformtext_minsize=8,
        uniformtext_mode="hide",
        bargap=0.15,
        bargroupgap=0.1,
    )

    # --- Monthly Tokens by Source (Pie Subplots) ---
    tsdf = tokens_source_df.copy()
    tsdf["Date"] = pd.to_datetime(tsdf["Date"], errors="coerce")
    tsdf = tsdf[tsdf["Date"] >= "2025-01-01"].dropna(subset=["Date"])
    tsdf["Month_dt"] = tsdf["Date"].dt.to_period("M").dt.to_timestamp()
    tsdf["Month"] = tsdf["Month_dt"].dt.strftime("%b %Y")
    tsdf = tsdf.sort_values("Month_dt")
    month_order = tsdf["Month"].unique().tolist()
    tsdf["Month"] = pd.Categorical(tsdf["Month"], categories=month_order, ordered=True)

    token_source_cols = [ col for col in tsdf.columns if col not in ["Date", "Month_dt", "Month", "Total"] and pd.api.types.is_numeric_dtype(tsdf[col]) ]
    melted = tsdf.melt( id_vars="Month", value_vars=token_source_cols, var_name="Source", value_name="Tokens",)
    monthly_data = (melted.groupby(["Month", "Source"], observed=True).sum().reset_index())
    months = monthly_data["Month"].cat.categories.tolist()
    month_totals = (monthly_data.groupby("Month", observed=True)["Tokens"].sum().to_dict())
    subplot_titles = [f"{m}" for m in months]

    fig_pies = make_subplots(
        rows=1,
        cols=len(months),
        specs=[[{"type": "domain"}] * len(months)],
        subplot_titles=subplot_titles,
    )
    annotations = []
    for i, month in enumerate(months):
        sub_df = monthly_data[monthly_data["Month"] == month]
        fig_pies.add_trace(
            go.Pie(
                labels=sub_df["Source"],
                values=sub_df["Tokens"],
                name=str(month),
                textinfo="percent",
                text=sub_df["Source"],
                textposition="inside",
                hovertemplate="%{label}: %{value:,.0f} tokens (%{percent})",
                marker=dict(colors=px.colors.qualitative.Pastel),
            ),
            row=1,
            col=i + 1,
        )
        annotations.append(
            dict(
                x=(i + 0.5) / len(months),
                y=-0.25,
                text=f"<b style='font-size:16px'>Total: {int(sub_df['Tokens'].sum()):,}</b>",
                showarrow=False,
                xanchor="center",
                font=dict(size=16),
                xref="paper",
                yref="paper",
            )
        )

    fig_pies.update_layout(
        title_text=f"Monthly Token Distribution by Source (Total: {int(monthly_data['Tokens'].sum()):,})",
        margin=dict(t=100, b=80),
        annotations=fig_pies.layout.annotations + tuple(annotations),
    )

    return token_bar, token_line, wallet_pie, wallet_bar, referral_bar, referral_line, fee_line, token_source_bar, fig_pies

# --- Generate charts once ---
token_bar, token_line, wallet_pie, wallet_bar, referral_bar, referral_line, fee_line, token_source_bar, fig_pies = create_figures()

# --- Dash App ---
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.title = "Sharp Token Dashboard"

app.layout = dbc.Container(
    [
        html.H2("Sharp Token Dashboard", className="my-4 text-center"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(figure=token_bar), md=6),
                dbc.Col(dcc.Graph(figure=token_line), md=6),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(figure=wallet_pie), md=6),
                dbc.Col(dcc.Graph(figure=wallet_bar), md=6),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(figure=referral_bar), md=6),
                dbc.Col(dcc.Graph(figure=referral_line), md=6),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(figure=fee_line), md=6),
                dbc.Col(dcc.Graph(figure=token_source_bar), md=6),
            ],
            className="mb-4",
        ),
        dbc.Row([dbc.Col(dcc.Graph(figure=fig_pies), md=12)], className="mb-4"),
    ],
    fluid=False,
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0')
    #app.run(debug=True)
