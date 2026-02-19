"""
Black-Scholes-Merton option pricing and Greeks calculator.

Supports European options with continuous dividend yield (q).
All formulas follow the Merton (1973) extension of Black-Scholes (1973).
"""

import numpy as np
from scipy.stats import norm


class OptionGreeks:
    """
    European option pricer and Greeks calculator using Black-Scholes-Merton.

    Parameters
    ----------
    S     : float — Current spot price of the underlying asset.
    K     : float — Strike price of the option.
    T     : float — Time to expiration in *years* (e.g. 30/365 for 30-day option).
    r     : float — Continuously compounded risk-free rate (e.g. 0.05 for 5%).
    sigma : float — Annualised implied/historical volatility (e.g. 0.20 for 20%).
    q     : float — Continuous dividend yield (default 0.0, i.e. no dividends).

    Example
    -------
    >>> opt = OptionGreeks(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
    >>> opt.price()
    {'call': 10.450584, 'put': 5.573526}
    >>> opt.delta()
    {'call': 0.636831, 'put': -0.363169}
    """

    def __init__(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
    ) -> None:
        if T <= 0:
            raise ValueError(
                f"T (time to expiration) must be > 0, got T={T}. "
                "Use T = days_to_expiry / 365."
            )
        if sigma <= 0:
            raise ValueError(
                f"sigma (volatility) must be > 0, got sigma={sigma}. "
                "Typical range: 0.05 (5%) to 2.00 (200%)."
            )
        if S <= 0:
            raise ValueError(f"S (spot price) must be > 0, got S={S}.")
        if K <= 0:
            raise ValueError(f"K (strike price) must be > 0, got K={K}.")

        self.S = float(S)
        self.K = float(K)
        self.T = float(T)
        self.r = float(r)
        self.sigma = float(sigma)
        self.q = float(q)

        # Pre-compute d1 / d2 once; all Greeks reuse them.
        self._d1, self._d2 = self._d1_d2()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _d1_d2(self) -> tuple[float, float]:
        """
        Compute the standardised normal variates d1 and d2.

        Black-Scholes-Merton formulae:

            d1 = [ln(S/K) + (r - q + σ²/2) · T] / (σ · √T)
            d2 = d1 - σ · √T

        d1 is related to the *risk-adjusted* probability that the option
        expires in-the-money; d2 is the *risk-neutral* probability ITM.
        """
        ln_SK = np.log(self.S / self.K)                     # log-moneyness
        drift = (self.r - self.q + 0.5 * self.sigma ** 2)   # adjusted drift
        vol_sqrt_T = self.sigma * np.sqrt(self.T)            # total vol over T

        d1 = (ln_SK + drift * self.T) / vol_sqrt_T
        d2 = d1 - vol_sqrt_T
        return d1, d2

    # ------------------------------------------------------------------
    # Price
    # ------------------------------------------------------------------

    def price(self) -> dict[str, float]:
        """
        European call and put prices under BSM.

        Formulae
        --------
            Call = S·e^(-q·T)·N(d1) − K·e^(-r·T)·N(d2)
            Put  = K·e^(-r·T)·N(-d2) − S·e^(-q·T)·N(-d1)

        where N(·) is the standard normal CDF.

        Returns
        -------
        dict with keys 'call' and 'put' (both in the same currency as S/K).
        """
        S, K, T, r, q = self.S, self.K, self.T, self.r, self.q
        d1, d2 = self._d1, self._d2

        # Discount factors
        disc_r = np.exp(-r * T)   # risk-free discount
        disc_q = np.exp(-q * T)   # dividend discount (1 if q=0)

        call = S * disc_q * norm.cdf(d1) - K * disc_r * norm.cdf(d2)
        put  = K * disc_r * norm.cdf(-d2) - S * disc_q * norm.cdf(-d1)

        return {
            "call": round(float(call), 6),
            "put":  round(float(put),  6),
        }

    # ------------------------------------------------------------------
    # Delta  (∂V/∂S)
    # ------------------------------------------------------------------

    def delta(self) -> dict[str, float]:
        """
        First-order sensitivity of option price to a $1 move in the spot.

        Formulae
        --------
            Δ_call =  e^(-q·T) · N(d1)       range [0, +1]
            Δ_put  = -e^(-q·T) · N(-d1)      range [-1,  0]

        Interpretation
        --------------
        Δ = 0.60 means the option price moves ~$0.60 for each $1 the
        underlying moves.  |Δ| ≈ probability of expiring ITM (rough
        guide; exact only when q = 0 and r = 0).

        Returns
        -------
        dict with keys 'call' and 'put'.
        """
        disc_q = np.exp(-self.q * self.T)

        call_delta = disc_q * norm.cdf(self._d1)
        put_delta  = -disc_q * norm.cdf(-self._d1)

        return {
            "call": round(float(call_delta), 6),
            "put":  round(float(put_delta),  6),
        }

    # ------------------------------------------------------------------
    # Gamma  (∂²V/∂S²  =  ∂Δ/∂S)
    # ------------------------------------------------------------------

    def gamma(self) -> float:
        """
        Rate of change of Delta with respect to the spot price.

        Formula
        -------
            Γ = e^(-q·T) · N'(d1) / (S · σ · √T)

        where N'(·) is the standard normal PDF.

        Notes
        -----
        - Gamma is identical for calls and puts (put-call symmetry).
        - High Gamma near ATM / near expiry — Delta changes quickly.
        - Important for risk management of Delta-hedged portfolios.

        Returns
        -------
        float (always >= 0).
        """
        disc_q = np.exp(-self.q * self.T)
        vol_sqrt_T = self.sigma * np.sqrt(self.T)

        gamma_val = disc_q * norm.pdf(self._d1) / (self.S * vol_sqrt_T)

        return round(float(gamma_val), 6)

    # ------------------------------------------------------------------
    # Vega  (∂V/∂σ)
    # ------------------------------------------------------------------

    def vega(self) -> float:
        """
        Sensitivity of option price to a unit change in implied volatility.

        Formula
        -------
            ν = S · e^(-q·T) · N'(d1) · √T

        Units
        -----
        This implementation returns vega per 1% move in volatility
        (i.e. the raw BSM vega divided by 100).  So if vega = 0.38,
        a 1 pp rise in IV from 20% → 21% increases the option value ~$0.38.

        Notes
        -----
        - Vega is identical for calls and puts.
        - Maximised at ATM; decays as the option moves far ITM or OTM.

        Returns
        -------
        float (always >= 0), in currency units per 1% vol change.
        """
        disc_q = np.exp(-self.q * self.T)

        # Raw vega (per unit sigma, i.e. per 100% vol move)
        raw_vega = self.S * disc_q * norm.pdf(self._d1) * np.sqrt(self.T)

        # Convert to per-1%-vol-point (divide by 100)
        vega_per_pct = raw_vega / 100.0

        return round(float(vega_per_pct), 6)

    # ------------------------------------------------------------------
    # Theta  (∂V/∂t  — time decay)
    # ------------------------------------------------------------------

    def theta(self) -> dict[str, float]:
        """
        Rate of change of option price with respect to the passage of time.

        Formulae (annualised first, then converted to *per calendar day*)
        --------
            θ_call = -[S·e^(-q·T)·N'(d1)·σ / (2√T)]
                     - r·K·e^(-r·T)·N(d2)
                     + q·S·e^(-q·T)·N(d1)

            θ_put  = -[S·e^(-q·T)·N'(d1)·σ / (2√T)]
                     + r·K·e^(-r·T)·N(-d2)
                     - q·S·e^(-q·T)·N(-d1)

        Units
        -----
        Returns theta **per calendar day** (divide annualised by 365).
        A theta of -0.05 means the option loses ~$0.05 in value each day,
        all else being equal.

        Returns
        -------
        dict with keys 'call' and 'put' (both negative for long options).
        """
        S, K, T, r, q = self.S, self.K, self.T, self.r, self.q
        d1, d2 = self._d1, self._d2
        disc_r = np.exp(-r * T)
        disc_q = np.exp(-q * T)
        vol_sqrt_T = self.sigma * np.sqrt(T)

        # Shared first term (time decay from vol)
        decay_term = -S * disc_q * norm.pdf(d1) * self.sigma / (2.0 * np.sqrt(T))

        theta_call = (
            decay_term
            - r * K * disc_r * norm.cdf(d2)
            + q * S * disc_q * norm.cdf(d1)
        )
        theta_put = (
            decay_term
            + r * K * disc_r * norm.cdf(-d2)
            - q * S * disc_q * norm.cdf(-d1)
        )

        # Convert from annual to per-day
        return {
            "call": round(float(theta_call / 365.0), 6),
            "put":  round(float(theta_put  / 365.0), 6),
        }

    # ------------------------------------------------------------------
    # Rho  (∂V/∂r)
    # ------------------------------------------------------------------

    def rho(self) -> dict[str, float]:
        """
        Sensitivity of option price to a unit change in the risk-free rate.

        Formulae
        --------
            ρ_call =  K · T · e^(-r·T) · N(d2)
            ρ_put  = -K · T · e^(-r·T) · N(-d2)

        Units
        -----
        Returns rho per 1% move in interest rates (raw / 100).
        So rho = 0.25 means a 1 pp rise in r increases the call by ~$0.25.

        Notes
        -----
        - Calls have positive rho (higher rates → calls worth more).
        - Puts have negative rho (higher rates → puts worth less).
        - Effect is small for short-dated options; grows with T.

        Returns
        -------
        dict with keys 'call' and 'put'.
        """
        K, T, r = self.K, self.T, self.r
        disc_r = np.exp(-r * T)
        d2 = self._d2

        rho_call =  K * T * disc_r * norm.cdf(d2)
        rho_put  = -K * T * disc_r * norm.cdf(-d2)

        # Per 1% rate move
        return {
            "call": round(float(rho_call / 100.0), 6),
            "put":  round(float(rho_put  / 100.0), 6),
        }

    # ------------------------------------------------------------------
    # Convenience repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"OptionGreeks(S={self.S}, K={self.K}, T={self.T:.6f}, "
            f"r={self.r}, sigma={self.sigma}, q={self.q})"
        )

    def summary(self) -> dict:
        """
        Return all Greeks and prices in a single dictionary.

        Returns
        -------
        dict with keys: price, delta, gamma, vega, theta, rho.
        """
        return {
            "price": self.price(),
            "delta": self.delta(),
            "gamma": self.gamma(),
            "vega":  self.vega(),
            "theta": self.theta(),
            "rho":   self.rho(),
        }


# ---------------------------------------------------------------------------
# Quick sanity-check
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # ATM 1-year European option — widely cited BSM benchmark values
    option = OptionGreeks(S=100, K=100, T=1.0, r=0.05, sigma=0.20)

    print("=" * 50)
    print("Black-Scholes-Merton — Benchmark (q=0)")
    print("  S=100  K=100  T=1yr  r=5%  σ=20%")
    print("=" * 50)

    prices = option.price()
    print(f"  Call price : {prices['call']:.6f}   (expected ~10.450584)")
    print(f"  Put  price : {prices['put']:.6f}   (expected ~5.573526)")

    deltas = option.delta()
    print(f"  Delta call : {deltas['call']:.6f}   (expected ~0.636831)")
    print(f"  Delta put  : {deltas['put']:.6f}  (expected ~-0.363169)")

    print(f"  Gamma      : {option.gamma():.6f}   (expected ~0.018762)")
    print(f"  Vega/1%    : {option.vega():.6f}   (expected ~0.375241)")

    thetas = option.theta()
    print(f"  Theta call : {thetas['call']:.6f}  (per day, expected ~-0.017440)")
    print(f"  Theta put  : {thetas['put']:.6f}  (per day, expected ~-0.004903)")

    rhos = option.rho()
    print(f"  Rho   call : {rhos['call']:.6f}   (per 1%, expected ~0.532325)")
    print(f"  Rho   put  : {rhos['put']:.6f}  (per 1%, expected ~-0.418875)")

    print()
    print("— With dividend yield q=3% —")
    opt_div = OptionGreeks(S=100, K=100, T=1.0, r=0.05, sigma=0.20, q=0.03)
    s = opt_div.summary()
    print(f"  Call price : {s['price']['call']:.6f}")
    print(f"  Delta call : {s['delta']['call']:.6f}")
    print(f"  Gamma      : {s['gamma']:.6f}")

    print()
    print("— Edge-case guards —")
    try:
        OptionGreeks(S=100, K=100, T=0.0, r=0.05, sigma=0.20)
    except ValueError as e:
        print(f"  T=0  caught: {e}")

    try:
        OptionGreeks(S=100, K=100, T=1.0, r=0.05, sigma=0.0)
    except ValueError as e:
        print(f"  σ=0  caught: {e}")
