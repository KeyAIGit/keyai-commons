package main

// Deliberately small, inspectable built-in workload. No downloaded code or data.
// A 2 -> 16 -> 1 neural network learns a synthetic noisy XOR classification task.
import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"math"
	"time"
)

const modelID = "tiny-xor-mlp-v1"
const hidden = 16
const weightCount = 65
const batchSize = 32
const maxSteps = 1200

type PRNG struct{ State uint64 }

func (r *PRNG) next() float64 {
	if r.State == 0 {
		r.State = 0x9e3779b97f4a7c15
	}
	x := r.State
	x ^= x >> 12
	x ^= x << 25
	x ^= x >> 27
	r.State = x
	return float64((x*2685821657736338717)>>11) / 9007199254740992.0
}
func initialWeights() []float64 {
	r := PRNG{20260917}
	w := make([]float64, weightCount)
	for i := range w {
		w[i] = (r.next()*2 - 1) * 0.6
	}
	return w
}
func sample(r *PRNG) (float64, float64, float64) {
	x := r.next()*2 - 1
	y := r.next()*2 - 1
	label := 0.0
	if (x > 0) != (y > 0) {
		label = 1
	}
	return x, y, label
}
func forward(w []float64, x, y float64) (float64, [hidden]float64) {
	var h [hidden]float64
	z := w[64]
	for j := 0; j < hidden; j++ {
		h[j] = math.Tanh(w[j*2]*x + w[j*2+1]*y + w[32+j])
		z += w[48+j] * h[j]
	}
	z = math.Max(-40, math.Min(40, z))
	return 1 / (1 + math.Exp(-z)), h
}
func validWeights(w []float64) bool {
	if len(w) != weightCount {
		return false
	}
	for _, v := range w {
		if math.IsNaN(v) || math.IsInf(v, 0) || math.Abs(v) > 50 {
			return false
		}
	}
	return true
}
func hashWeights(w []float64) string {
	b, _ := json.Marshal(w)
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}
func evaluate(w []float64) (float64, float64) {
	r := PRNG{9912345}
	loss, correct := 0.0, 0.0
	for i := 0; i < 4096; i++ {
		x, y, t := sample(&r)
		p, _ := forward(w, x, y)
		p = math.Max(1e-12, math.Min(1-1e-12, p))
		loss -= t*math.Log(p) + (1-t)*math.Log(1-p)
		if (p >= 0.5) == (t == 1) {
			correct++
		}
	}
	return loss / 4096, correct / 4096
}
func trainModel(ctx context.Context, base []float64, seed uint64, steps int, paced bool, progress func(int)) ([]float64, error) {
	duty := 0
	if paced {
		duty = 25
	}
	return trainWithDuty(ctx, base, seed, steps, duty, progress)
}

func trainWithDuty(ctx context.Context, base []float64, seed uint64, steps, duty int, progress func(int)) ([]float64, error) {
	if duty != 0 && duty != 10 && duty != 25 && duty != 50 {
		return nil, errors.New("invalid CPU duty target")
	}
	if !validWeights(base) || steps < 1 || steps > maxSteps || seed == 0 {
		return nil, errors.New("invalid bounded training task")
	}
	w := append([]float64(nil), base...)
	r := PRNG{seed}
	for step := 0; step < steps; step++ {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
		}
		began := time.Now()
		var g [weightCount]float64
		for b := 0; b < batchSize; b++ {
			x, y, t := sample(&r)
			p, h := forward(w, x, y)
			dz := p - t
			g[64] += dz
			for j := 0; j < hidden; j++ {
				g[48+j] += dz * h[j]
				dh := dz * w[48+j] * (1 - h[j]*h[j])
				g[2*j] += dh * x
				g[2*j+1] += dh * y
				g[32+j] += dh
			}
		}
		for i := range w {
			w[i] -= 0.12 * g[i] / batchSize
		}
		if progress != nil && (step%10 == 0 || step == steps-1) {
			progress(step + 1)
		}
		if duty > 0 {
			// One training goroutine; aim at <=25% of one logical CPU, with an
			// additional 5ms inter-batch floor. This is not an OS-enforced power cap.
			delay := time.Duration(100/duty-1) * time.Since(began)
			if delay < 5*time.Millisecond {
				delay = 5 * time.Millisecond
			}
			timer := time.NewTimer(delay)
			select {
			case <-ctx.Done():
				timer.Stop()
				return nil, ctx.Err()
			case <-timer.C:
			}
		}
	}
	if !validWeights(w) {
		return nil, errors.New("non-finite training output")
	}
	return w, nil
}
