import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


def OF(win_rate, reward_risk, n):
    n_w = n*win_rate
    n_l = n - n_w
    p = win_rate * (reward_risk + 1) - 1
    l = p/reward_risk
    if p < 0 or l < 0:
        return 0

    of = (1+p)**(n_w) * (1-l) ** (n_l)
    return (1+p)**(n_w) * (1-l) ** (n_l)

def get_p_l(win_rate, reward_risk):
    p = win_rate * (reward_risk + 1) - 1
    l = p/reward_risk
    return p, l

N = 4

def on_click(event):
    global N
    # Check if the click was on the plot
    if event.inaxes is not None:
        r_value = event.xdata
        wr_value = event.ydata
        Of = OF(win_rate =wr_value, reward_risk=r_value, n=N) if r_value != 0 else 0

        p, l = get_p_l(win_rate=wr_value, reward_risk=r_value)

        plt.plot(r_value, wr_value, 'ro')  # 'ro' denotes red color, circle marker
        plt.annotate(f'${{T_{{wr}}}}$={Of:.2f}\n$w_r$={wr_value:.2f}\n$r$={r_value:.2f}\n$p$={p:.2f}\n$l$={l:.2f}',
                     xy=(r_value, wr_value), xytext=(r_value + 0.2, wr_value+0.1),
                     arrowprops=dict(facecolor='black', shrink=0.05))
        plt.draw()  # Redraw the plot to show the new annotation


# Define a range of values for w_r and r
w_r_values = np.linspace(0.1, 0.7, 500)  # w_r varies between 0 and 1
r_values = np.linspace(0.5, 3, 500)  # Assuming r varies between 0.5 and 5 for illustration

# Initialize a 2D array to store the values of the constant
Of = np.zeros((len(w_r_values), len(r_values)))

# Calculate the constant for each combination of w_r and r
for i, w_r in enumerate(w_r_values):
    for j, r in enumerate(r_values):
        Of[i, j] = OF(win_rate =w_r, reward_risk=r, n=N) if r != 0 else 0  # Avoid division by zero
        if abs(Of[i, j] - 1.0) < 0.001:
            Of[i, j] = 1.0
# Plot the result
plt.figure(figsize=(10, 7))

cp = plt.contourf(r_values, w_r_values, Of, cmap='turbo')

plt.colorbar(cp, pad = 0.1)


# Adding a contour line for Of = 1
cs = plt.contour(r_values, w_r_values, Of, levels=[1], colors='r')
fmt = {1: '$\\mathcal{O}_{f}$ = 1'}  # the label for level 1 contour
plt.clabel(cs, fmt=fmt, inline=True, fontsize=10)

plt.title('Optimality factor $\\mathcal{O}_{f}$ for varying $w_r$ and $r$ and $n$=4')
plt.xlabel('Reward to risk ratio $r$')
plt.ylabel('Win ratio $w_r$')


# Calculate and draw the contour line for w_r = 0.5
try:
    w_r = 0.5
    Of_wr_05 = [OF(win_rate=w_r, reward_risk=r, n=N) if r != 0 else 0 for r in r_values]

    plt.plot(r_values, [w_r] * len(r_values), 'g--')  # 'g--' denotes green color, dashed line

except Exception as e:
    print(f"Unable to draw contour for w_r=0.5: {e}")


# Connect the click event to the callback function
plt.gcf().canvas.mpl_connect('button_press_event', on_click)

plt.show()

print(OF(win_rate=0.5, reward_risk=3.0, n=N))
print(get_p_l(win_rate=0.5, reward_risk=3.0))
