from mmap import MAP_EXECUTABLE
import sys
import jax.numpy as jnp
from dmff.admp.spatial import v_pbc_shift
import numpy as np
import jax.numpy as jnp
from jax import grad


class LennardJonesForce:
    def __init__(self,
                 r_switch,
                 r_cut,
                 map_prm,
                 map_nbfix,
                 map_exclusion,
                 map_14,
                 scale14=0.0,
                 isShift=False,
                 isSwitch=False) -> None:

        self.isShift = isShift
        self.isSwitch = isSwitch
        self.r_switch = r_switch
        self.r_cut = r_cut

        self.map_prm = map_prm
        self.map_nbfix = map_nbfix
        self.map_exclusion = map_exclusion
        self.map_14 = map_14

    def generate_get_energy(self):
        def get_LJ_energy(dr_vec, sig, eps, box):
            dr_vec = v_pbc_shift(dr_vec, box, jnp.linalg.inv(box))
            dr_norm = jnp.linalg.norm(dr_vec, axis=1)
            dr_norm = dr_norm[dr_norm <= self.r_cut]

            dr_inv = 1.0 / dr_norm
            sig_dr = sig * dr_inv
            sig_dr12 = jnp.power(sig_dr, 12)
            sig_dr6 = jnp.power(sig_dr, 6)
            E = 4 * eps * (sig_dr12 - sig_dr6)

            shiftedE = 0

            if self.isShift:

                rcut_inv = 1.0 / self.r_cut
                sig_rcut = sig * rcut_inv
                sig_rcut12 = jnp.power(sig_rcut, 12)
                sig_rcut6 = jnp.power(sig_rcut, 6)
                shiftedE = 4 * eps * (sig_rcut12 - sig_rcut6)

            if self.isSwitch:

                x = (dr_norm - self.r_switch) / (self.r_cut - self.r_switch)
                S = 1 - 6 * x**5 + 15 * x**4 - 10 * x**3
                jnp.where(dr_norm > self.r_switch, E, E * S)

            return jnp.sum(E) + shiftedE

        def get_energy(positions, box, pairs, epsilon, sigma, epsfix, sigfix):
            eps_m1 = jnp.repeat(epsilon.reshape((-1, 1)),
                                epsilon.shape[0],
                                axis=1)
            eps_m2 = eps_m1.T
            eps_mat = jnp.sqrt(eps_m1 * eps_m2)
            sig_m1 = jnp.repeat(sigma.reshape((-1, 1)), sigma.shape[0], axis=1)
            sig_m2 = sig_m1.T
            sig_mat = (sig_m1 + sig_m2) * 0.5

            eps_mat = eps_mat.at[self.map_nbfix[:, 0], self.map_nbfix[:, 1]].set(epsfix)
            eps_mat = eps_mat.at[self.map_nbfix[:, 1], self.map_nbfix[:, 0]].set(epsfix)
            sig_mat = sig_mat.at[self.map_nbfix[:, 0], self.map_nbfix[:, 1]].set(sigfix)
            sig_mat = sig_mat.at[self.map_nbfix[:, 1], self.map_nbfix[:, 0]].set(sigfix)

            dr_vec = positions[pairs[:, 0]] - positions[pairs[:, 1]]
            prm_pair0 = self.map_prm[pairs[:, 0]]
            prm_pair1 = self.map_prm[pairs[:, 1]]
            eps = eps_mat[prm_pair0, prm_pair1]
            sig = sig_mat[prm_pair0, prm_pair1]

            E_inter = get_LJ_energy(dr_vec, sig, eps, box)

            # exclusion
            dr_excl_vec = positions[self.map_exclusion[:, 0]] - positions[
                self.map_exclusion[:, 1]]
            excl_map0 = self.map_prm[self.map_exclusion[:, 0]]
            excl_map1 = self.map_prm[self.map_exclusion[:, 1]]
            eps_excl = eps_mat[excl_map0, excl_map1]
            sig_excl = sig_mat[excl_map0, excl_map1]

            E_excl = get_LJ_energy(dr_excl_vec, sig_excl, eps_excl, box)

            return E_inter - E_excl

        return get_energy


class CoulombForce:
    pass


if __name__ == '__main__':

    # atoms: 0, 1, 2, 3
    # exclusion: 0 - 1, 2 - 3
    # nbfix: 0 - 3 (3., 0.3)
    positions = jnp.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 0, 1]],
                          dtype=float)

    box = jnp.array([[10, 0, 0], [0, 10, 0], [0, 0, 10]])

    pairs = np.array([[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]])

    epsilon = jnp.array([1., 2.])
    sigma = jnp.array([0.1, 0.2])

    map_prm = np.array([0, 0, 1, 1])
    map_nbfix = np.array([[0, 3]])
    epsfix = jnp.array([3.])
    sigfix = jnp.array([0.3])
    map_exclusion = np.array([[0, 1], [2, 3]])
    map_14 = np.array([[]])

    lj = LennardJonesForce(0, 3, map_prm, map_nbfix, map_exclusion, map_14)
    get_energy = lj.generate_get_energy()

    E = get_energy(positions, box, pairs, epsilon, sigma, epsfix, sigfix)
    print(E)
    F = grad(get_energy)(positions, box, pairs, epsilon, sigma, epsfix, sigfix)
    print(F)